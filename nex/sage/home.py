"""Partnership home, first-run coach, and slash-command capture helpers.

UX Recs 1–5 support: status home, coach, capture parsing, open-summary text,
Partner vs Rails labels. Pure logic — no mocks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .local_models import LocalModel, discover_local_models, pick_default_local
from .partner import (
    Commitment,
    PersonStub,
    SageProfile,
    load_or_create_profile,
)


# Rec 5 — fixed role labels (use in CLI, TUI, WattOS)
LABEL_PARTNER = "Partner (local Sage)"
LABEL_RAILS = "Rails (supervise / agent / Grok)"
ROLE_BLURB = (
    f"{LABEL_PARTNER}: purpose, people, direction — local MLX voice.\n"
    f"{LABEL_RAILS}: policy + optional Grok for hard agent decisions — "
    "Grok is not your sage voice."
)


@dataclass
class HomeSnapshot:
    profile_id: str
    north_star: str
    people_count: int
    open_commits: int
    sit_count: int
    reflection_count: int
    values_note: str
    last_sit_goal: str
    last_sit_ok: Optional[bool]
    model_ready: bool
    model_label: str
    model_path: str
    grok_available: bool
    grok_model: str
    profile_path: str
    needs_coach: bool
    coach_reasons: List[str] = field(default_factory=list)
    open_commit_lines: List[str] = field(default_factory=list)
    people_lines: List[str] = field(default_factory=list)


def _grok_status() -> Tuple[bool, str]:
    try:
        from ..envload import ensure_env_loaded
        from ..grok_escalator import GrokEscalator

        ensure_env_loaded()
        e = GrokEscalator()
        return e.is_available(), e.model or "grok-3"
    except Exception:
        return False, "unavailable"


def build_home_snapshot(
    profile_id: str = "default",
    *,
    base: Optional[Path] = None,
) -> HomeSnapshot:
    prof = load_or_create_profile(profile_id, base=base)
    d = prof.build_direction()
    open_c = [c for c in prof.commitments if not c.done]
    sits = [s for s in prof.sit_log if s.get("sit_id")]
    last = sits[-1] if sits else {}
    local = pick_default_local()
    ready = local is not None and local.complete
    grok_ok, grok_model = _grok_status()

    reasons: List[str] = []
    if not ready:
        reasons.append("No complete local MLX model (READY) on disk")
    if not prof.people:
        reasons.append("No people on your mattering map yet")
    if not open_c and not sits and not prof.reflections:
        reasons.append("No sits, commitments, or reflections yet — partnership record is empty")

    return HomeSnapshot(
        profile_id=prof.profile_id,
        north_star=(d.get("north_star") or "").strip() or "(no direction yet — talk or add people/commits)",
        people_count=len(prof.people),
        open_commits=len(open_c),
        sit_count=len(sits),
        reflection_count=len(prof.reflections),
        values_note=prof.values_note,
        last_sit_goal=str(last.get("co_goal") or ""),
        last_sit_ok=last.get("ok") if last else None,
        model_ready=bool(ready),
        model_label=local.label if local else "(none)",
        model_path=local.path if local else "",
        grok_available=grok_ok,
        grok_model=grok_model,
        profile_path=str(prof.path(base)),
        needs_coach=bool(reasons),
        coach_reasons=reasons,
        open_commit_lines=[f"[{c.toward_person}] {c.text}" + (f" (due {c.due})" if c.due else "") for c in open_c[:8]],
        people_lines=[f"{p.name} ({p.relation})" for p in prof.people[:12]],
    )


def render_home_text(snap: HomeSnapshot) -> str:
    """Plain multi-line home for CLI / tests."""
    lines = [
        "══════════════════════════════════════════",
        "  MLX-SAGE · Partnership home",
        f"  Mode: {LABEL_PARTNER}",
        "══════════════════════════════════════════",
        "",
        ROLE_BLURB,
        "",
        f"Profile: {snap.profile_id}",
        f"North star: {snap.north_star}",
        f"People: {snap.people_count}  |  Open commits: {snap.open_commits}  |  Sits: {snap.sit_count}  |  Reflections: {snap.reflection_count}",
        f"Values: {snap.values_note}",
    ]
    if snap.last_sit_goal:
        flag = "ok" if snap.last_sit_ok else "redirect"
        lines.append(f"Last sit [{flag}]: {snap.last_sit_goal}")
    lines.append("")
    lines.append("--- Local model (Partner voice) ---")
    if snap.model_ready:
        lines.append(f"READY · {snap.model_label}")
    else:
        lines.append("NOT READY · no complete MLX chat model found")
    lines.append("")
    lines.append("--- Grok (Rails only — not sage voice) ---")
    if snap.grok_available:
        lines.append(f"Available · model {snap.grok_model} (XAI) · use via supervise / GROK_IN_LOOP agent")
    else:
        lines.append("Unavailable · set XAI_API_KEY in .env for Rails escalation")
    if snap.people_lines:
        lines.append("")
        lines.append("People:")
        for p in snap.people_lines:
            lines.append(f"  · {p}")
    if snap.open_commit_lines:
        lines.append("")
        lines.append("Open commitments:")
        for c in snap.open_commit_lines:
            lines.append(f"  · {c}")
    lines.append("")
    lines.append("--- Next actions ---")
    if snap.needs_coach:
        lines.append("  1. nex sage coach          # first-run guide (model + profile)")
    lines.append("  2. nex sage tui            # talk with your partner (local MLX)")
    lines.append("  3. nex sage people add …   # who matters")
    lines.append("  4. nex sage commit …       # one small act")
    lines.append("  5. nex sage receipt        # detailed receipt")
    lines.append("")
    lines.append(f"Rails (optional coding): nex supervise · nex agent  [{LABEL_RAILS}]")
    lines.append(f"Profile file: {snap.profile_path}")
    return "\n".join(lines)


def render_open_ritual_markdown(snap: HomeSnapshot) -> str:
    """Welcome-back block for Sage TUI open (Rec 4)."""
    lines = [
        f"### Welcome back · {LABEL_PARTNER}",
        "",
        f"**North star:** {snap.north_star}",
        "",
        f"People **{snap.people_count}** · open commits **{snap.open_commits}** · sits **{snap.sit_count}**",
        "",
    ]
    if snap.open_commit_lines:
        lines.append("**Open commitments**")
        for c in snap.open_commit_lines[:5]:
            lines.append(f"- {c}")
        lines.append("")
    if snap.people_lines:
        lines.append("**People**")
        for p in snap.people_lines[:5]:
            lines.append(f"- {p}")
        lines.append("")
    lines.append(
        "Talk naturally. Capture anytime: `/commit …` · `/person …` · `/direction` · `/receipt` · `/help`"
    )
    lines.append("")
    lines.append(
        f"*Grok ({snap.grok_model if snap.grok_available else 'off'}) is for {LABEL_RAILS}, not this chat.*"
    )
    return "\n".join(lines)


def render_coach_text(snap: HomeSnapshot) -> str:
    """First-run coach (Rec 2) — model + profile only, no supervise tour."""
    lines = [
        "══════════════════════════════════════════",
        "  MLX-SAGE · First-run coach",
        f"  Mode: {LABEL_PARTNER}",
        "══════════════════════════════════════════",
        "",
        "Goal: one local model + a thin living profile, then talk.",
        "We will not tour Superintendant / Grok here.",
        "",
    ]
    if snap.coach_reasons:
        lines.append("Why coach fired:")
        for r in snap.coach_reasons:
            lines.append(f"  · {r}")
        lines.append("")

    lines.append("### Step 1 — Local model (required for Partner voice)")
    if snap.model_ready:
        lines.append(f"  ✓ READY: {snap.model_label}")
    else:
        lines.append("  ✗ No complete model. Do one of:")
        lines.append("     nex models list")
        lines.append("     nex models recommend \"chat reasoning\" --max-memory 16")
        lines.append("     nex models download <alias-or-repo>")
        lines.append("     # or place full mlx-lm folder under ~/.mtplx/models/")
        lines.append("     nex sage models   # must show READY")
    lines.append("")
    lines.append("### Step 2 — Profile shell")
    lines.append(f"  nex sage init --profile {snap.profile_id}")
    lines.append("")
    lines.append("### Step 3 — Who matters (optional but high leverage)")
    lines.append(
        f'  nex sage people add --profile {snap.profile_id} --name Sam --relation sibling '
        f'--they-need-me "monthly call" --i-need "family continuity"'
    )
    lines.append("")
    lines.append("### Step 4 — One commitment (optional)")
    lines.append(
        f'  nex sage commit --profile {snap.profile_id} "Call Sam this week" --toward Sam'
    )
    lines.append("")
    lines.append("### Step 5 — Talk")
    lines.append(f"  nex sage tui --profile {snap.profile_id}")
    lines.append("")
    lines.append("Then return anytime:  nex sage   # or  nex home")
    lines.append("")
    lines.append(ROLE_BLURB)
    return "\n".join(lines)


@dataclass
class CaptureResult:
    ok: bool
    kind: str
    message: str
    updated_direction: bool = False


def parse_and_apply_capture(
    text: str,
    profile: SageProfile,
    *,
    base: Optional[Path] = None,
) -> Optional[CaptureResult]:
    """If text is a slash command, apply to profile and return result; else None (normal chat)."""
    raw = (text or "").strip()
    if not raw.startswith("/"):
        return None

    # split first token
    if " " in raw:
        cmd, rest = raw.split(" ", 1)
        rest = rest.strip()
    else:
        cmd, rest = raw, ""
    cmd = cmd.lower()

    if cmd in ("/help", "/?"):
        return CaptureResult(
            ok=True,
            kind="help",
            message=(
                "Capture commands (save to your profile, not just chat):\n"
                "  /commit <text> [| toward] [| due]\n"
                "  /person <Name> | <relation> [| they need me] [| I need them]\n"
                "  /reflect <one sentence>\n"
                "  /direction\n"
                "  /receipt  or  /home\n"
                "  /help\n"
                f"\n{ROLE_BLURB}"
            ),
        )

    if cmd in ("/receipt", "/home", "/status"):
        snap = build_home_snapshot(profile.profile_id, base=base)
        return CaptureResult(ok=True, kind="receipt", message=render_home_text(snap))

    if cmd == "/direction":
        path = profile.write_direction(base=base)
        d = profile.build_direction()
        north = d.get("north_star") or "(empty)"
        return CaptureResult(
            ok=True,
            kind="direction",
            message=f"Direction refreshed → {path}\n\nNorth star:\n{north}",
            updated_direction=True,
        )

    if cmd == "/reflect":
        if not rest:
            return CaptureResult(ok=False, kind="reflect", message="Usage: /reflect <one sentence for direction>")
        path = profile.add_reflection(rest, base=base)
        return CaptureResult(
            ok=True,
            kind="reflect",
            message=f"Saved reflection → direction updated ({path})",
            updated_direction=True,
        )

    if cmd == "/commit":
        if not rest:
            return CaptureResult(
                ok=False,
                kind="commit",
                message="Usage: /commit <text> [| toward person] [| due]",
            )
        parts = [p.strip() for p in rest.split("|")]
        text_c = parts[0] if parts else rest
        toward = parts[1] if len(parts) > 1 else "self"
        due = parts[2] if len(parts) > 2 else ""
        path = profile.add_commitment(
            Commitment(text=text_c, toward_person=toward or "self", due=due),
            base=base,
        )
        return CaptureResult(
            ok=True,
            kind="commit",
            message=f"Commitment saved [{toward}]: {text_c}\nDirection → {path}",
            updated_direction=True,
        )

    if cmd == "/person":
        if not rest:
            return CaptureResult(
                ok=False,
                kind="person",
                message="Usage: /person <Name> | <relation> [| they may need me] [| I need them]",
            )
        parts = [p.strip() for p in rest.split("|")]
        name = parts[0] if parts else ""
        relation = parts[1] if len(parts) > 1 else "person"
        they = parts[2] if len(parts) > 2 else ""
        i_need = parts[3] if len(parts) > 3 else ""
        if not name:
            return CaptureResult(ok=False, kind="person", message="Name required")
        path = profile.add_person(
            PersonStub(
                name=name,
                relation=relation or "person",
                they_may_need_me_for=they,
                i_need_them_for=i_need,
            ),
            base=base,
        )
        return CaptureResult(
            ok=True,
            kind="person",
            message=f"Person on map: {name} ({relation})\nDirection → {path}",
            updated_direction=True,
        )

    return CaptureResult(
        ok=False,
        kind="unknown",
        message=f"Unknown command {cmd}. Try /help",
    )
