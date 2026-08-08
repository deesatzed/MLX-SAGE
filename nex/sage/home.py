"""Partnership home, interactive setup, and slash-command capture.

Home is a short status card — not a command manual.
Coach is an interactive wizard that asks questions and writes the profile.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple

from .local_models import pick_default_local
from .partner import (
    Commitment,
    PersonStub,
    SageProfile,
    load_or_create_profile,
)

# Short labels (avoid dumping essay into every screen)
LABEL_PARTNER = "Partner"
LABEL_RAILS = "Rails"
ROLE_BLURB = (
    f"{LABEL_PARTNER}: local sage chat for purpose & people.\n"
    f"{LABEL_RAILS}: supervise/agent + optional Grok — not sage voice."
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
    needs_setup: bool  # empty partnership record or no model
    setup_reasons: List[str] = field(default_factory=list)
    open_commit_lines: List[str] = field(default_factory=list)
    people_lines: List[str] = field(default_factory=list)

    # Back-compat aliases used by older tests/callers
    @property
    def needs_coach(self) -> bool:
        return self.needs_setup

    @property
    def coach_reasons(self) -> List[str]:
        return self.setup_reasons


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
        reasons.append("no READY local model")
    empty_life = not prof.people and not open_c and not sits and not prof.reflections
    if empty_life:
        reasons.append("profile is still empty (no people / commits yet)")

    return HomeSnapshot(
        profile_id=prof.profile_id,
        north_star=(d.get("north_star") or "").strip()
        or "(none yet — add a person or talk in sage tui)",
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
        needs_setup=bool(reasons),
        setup_reasons=reasons,
        open_commit_lines=[
            f"{c.toward_person}: {c.text}" + (f" (due {c.due})" if c.due else "")
            for c in open_c[:8]
        ],
        people_lines=[f"{p.name} ({p.relation})" for p in prof.people[:12]],
    )


def render_home_text(snap: HomeSnapshot) -> str:
    """Short status card — no command cookbook."""
    model_line = (
        f"Model  ✓  {snap.model_label}"
        if snap.model_ready
        else "Model  ✗  none READY (run setup)"
    )
    # Partner home: hide Grok unless user cares — one quiet line
    life = f"{snap.people_count} people · {snap.open_commits} open commits · {snap.sit_count} sits"

    lines = [
        f"MLX-SAGE  ·  {LABEL_PARTNER}",
        f"Profile  {snap.profile_id}",
        "",
        f"North star",
        f"  {snap.north_star}",
        "",
        life,
        model_line,
    ]
    if snap.people_lines:
        lines.append("")
        lines.append("People")
        for p in snap.people_lines[:6]:
            lines.append(f"  · {p}")
    if snap.open_commit_lines:
        lines.append("")
        lines.append("Open commits")
        for c in snap.open_commit_lines[:6]:
            lines.append(f"  · {c}")

    lines.append("")
    if not snap.model_ready:
        lines.append("Next:  setup  (get a local model + thin profile)")
    elif snap.needs_setup:
        lines.append("Next:  setup  (add who matters)  or  talk")
    else:
        lines.append("Next:  talk")
    lines.append("")
    lines.append("Commands:  talk · setup · quit")
    lines.append(f"(advanced CLI still available; this menu is the happy path)")
    return "\n".join(lines)


def render_open_ritual_markdown(snap: HomeSnapshot) -> str:
    """Compact welcome for Sage TUI."""
    lines = [
        f"### {LABEL_PARTNER} · welcome",
        "",
        f"**{snap.north_star}**",
        "",
        f"{snap.people_count} people · {snap.open_commits} commits · model "
        f"{'ready' if snap.model_ready else 'missing'}",
        "",
    ]
    if snap.open_commit_lines:
        for c in snap.open_commit_lines[:4]:
            lines.append(f"- {c}")
        lines.append("")
    lines.append("Type to talk. Or: `/person …` `/commit …` `/help` · Ctrl+Q to leave")
    return "\n".join(lines)


def render_coach_text(snap: HomeSnapshot) -> str:
    """Non-interactive summary (rare). Prefer run_interactive_setup."""
    if snap.model_ready and not snap.needs_setup:
        return "You're set. Type: talk"
    lines = ["Setup checklist (interactive: run setup / nex sage setup)", ""]
    lines.append(f"Model: {'OK — ' + snap.model_label if snap.model_ready else 'need a READY local model'}")
    lines.append(f"People: {snap.people_count}")
    lines.append(f"Commits: {snap.open_commits}")
    if not snap.model_ready:
        lines.append("")
        lines.append("Get a model:  nex models download <name>  then  nex sage models")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Interactive UX (the fix for "wall of CLI recipes")
# ---------------------------------------------------------------------------

AskFn = Callable[[str, str], str]
ConfirmFn = Callable[[str, bool], bool]
PrintFn = Callable[[str], None]


def _default_ask(prompt: str, default: str = "") -> str:
    from rich.prompt import Prompt

    if default:
        return Prompt.ask(prompt, default=default).strip()
    return Prompt.ask(prompt).strip()


def _default_confirm(prompt: str, default: bool = True) -> bool:
    from rich.prompt import Confirm

    return bool(Confirm.ask(prompt, default=default))


def _default_print(msg: str) -> None:
    from rich.console import Console

    Console().print(msg)


def run_interactive_setup(
    profile_id: str = "default",
    *,
    base: Optional[Path] = None,
    ask: Optional[AskFn] = None,
    confirm: Optional[ConfirmFn] = None,
    emit: Optional[PrintFn] = None,
    launch_tui: bool = True,
) -> dict[str, Any]:
    """Walk the human through setup by *asking*, not dumping CLI strings.

    Returns a result dict for tests (what was done).
    """
    ask = ask or _default_ask
    confirm = confirm or _default_confirm
    emit = emit or _default_print

    result: dict[str, Any] = {
        "profile_id": profile_id,
        "person_added": None,
        "commit_added": None,
        "launch_tui": False,
        "blocked_no_model": False,
    }

    snap = build_home_snapshot(profile_id, base=base)
    emit("")
    emit("[bold]Setup[/bold] — a few questions. No command memorization.")
    emit("")

    # --- Model ---
    if not snap.model_ready:
        emit("[red]No READY local model.[/red] Partner chat needs one on disk.")
        emit("In another terminal (or after this):")
        emit("  nex models recommend \"chat\" --max-memory 16")
        emit("  nex models download <alias>")
        emit("  nex sage models")
        emit("")
        if not confirm("Continue setup without a model? (you can talk later)", False):
            result["blocked_no_model"] = True
            return result
    else:
        emit(f"[green]Model OK[/green]  {snap.model_label}")

    prof = load_or_create_profile(profile_id, base=base)
    prof.save(base=base)
    emit(f"Profile [cyan]{profile_id}[/cyan] ready.")

    # --- Person ---
    if confirm("Add someone who matters to you?", True):
        name = ask("  Their name", "")
        if name:
            relation = ask("  Relation (sibling, friend, spouse, …)", "person")
            they = ask("  They may need you for (optional)", "")
            i_need = ask("  You need them for (optional)", "")
            prof.add_person(
                PersonStub(
                    name=name,
                    relation=relation or "person",
                    they_may_need_me_for=they,
                    i_need_them_for=i_need,
                ),
                base=base,
            )
            result["person_added"] = name
            emit(f"[green]Saved[/green] {name} ({relation})")
        else:
            emit("[dim]Skipped person.[/dim]")
    else:
        emit("[dim]Skipped person.[/dim]")

    # --- Commitment ---
    if confirm("Add one small commitment for this week?", True):
        text = ask("  What will you do?", "")
        if text:
            toward = ask("  Toward whom / what?", result.get("person_added") or "self")
            prof.add_commitment(
                Commitment(text=text, toward_person=toward or "self"),
                base=base,
            )
            result["commit_added"] = text
            emit(f"[green]Saved commitment[/green] → {toward}")
        else:
            emit("[dim]Skipped commitment.[/dim]")
    else:
        emit("[dim]Skipped commitment.[/dim]")

    d = prof.build_direction()
    emit("")
    emit(f"[bold]North star now[/bold]\n  {d.get('north_star') or '(still forming)'}")
    emit("")

    if launch_tui and snap.model_ready and confirm("Open Partner chat now?", True):
        result["launch_tui"] = True
        emit("[dim]Starting sage tui…[/dim]")
        from .tui import run_sage_tui

        run_sage_tui(profile_id=profile_id, model_path=snap.model_path or None)
    elif not snap.model_ready:
        emit("When a model is READY:  nex sage talk")
    else:
        emit("When you want:  nex sage talk")

    return result


def run_home_menu(
    profile_id: str = "default",
    *,
    base: Optional[Path] = None,
    ask: Optional[AskFn] = None,
    confirm: Optional[ConfirmFn] = None,
    emit: Optional[PrintFn] = None,
) -> str:
    """Show short home, then a 3-choice menu: talk | setup | quit.

    Returns action taken: talk | setup | quit | none
    """
    ask = ask or _default_ask
    confirm = confirm or _default_confirm
    emit = emit or _default_print

    snap = build_home_snapshot(profile_id, base=base)
    emit(render_home_text(snap))
    emit("")

    choice = ask("What next? [talk / setup / quit]", "talk" if snap.model_ready else "setup")
    choice = (choice or "").strip().lower()
    if choice in ("t", "talk", "tui", "2"):
        if not snap.model_ready:
            emit("[red]No model yet.[/red] Choose setup, or install a model first.")
            return "none"
        from .tui import run_sage_tui

        run_sage_tui(profile_id=profile_id, model_path=snap.model_path or None)
        return "talk"
    if choice in ("s", "setup", "coach", "1"):
        run_interactive_setup(profile_id, base=base, ask=ask, confirm=confirm, emit=emit)
        return "setup"
    return "quit"


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
    """If text is a slash command, apply to profile and return result; else None."""
    raw = (text or "").strip()
    if not raw.startswith("/"):
        return None

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
                "In chat you can save to your profile:\n"
                "  /commit do X | toward person\n"
                "  /person Name | relation\n"
                "  /reflect one sentence\n"
                "  /direction   /receipt   /help"
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
            message=f"Direction updated.\n\n{north}",
            updated_direction=True,
        )

    if cmd == "/reflect":
        if not rest:
            return CaptureResult(ok=False, kind="reflect", message="Try: /reflect I want …")
        profile.add_reflection(rest, base=base)
        return CaptureResult(ok=True, kind="reflect", message="Saved to direction.", updated_direction=True)

    if cmd == "/commit":
        if not rest:
            return CaptureResult(ok=False, kind="commit", message="Try: /commit Call Sam | Sam")
        parts = [p.strip() for p in rest.split("|")]
        text_c = parts[0]
        toward = parts[1] if len(parts) > 1 else "self"
        due = parts[2] if len(parts) > 2 else ""
        profile.add_commitment(
            Commitment(text=text_c, toward_person=toward or "self", due=due),
            base=base,
        )
        return CaptureResult(
            ok=True,
            kind="commit",
            message=f"Commitment saved ({toward}): {text_c}",
            updated_direction=True,
        )

    if cmd == "/person":
        if not rest:
            return CaptureResult(
                ok=False,
                kind="person",
                message="Try: /person Sam | sibling",
            )
        parts = [p.strip() for p in rest.split("|")]
        name = parts[0] if parts else ""
        relation = parts[1] if len(parts) > 1 else "person"
        they = parts[2] if len(parts) > 2 else ""
        i_need = parts[3] if len(parts) > 3 else ""
        if not name:
            return CaptureResult(ok=False, kind="person", message="Name required")
        profile.add_person(
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
            message=f"Saved {name} ({relation})",
            updated_direction=True,
        )

    return CaptureResult(ok=False, kind="unknown", message=f"Unknown {cmd}. Try /help")
