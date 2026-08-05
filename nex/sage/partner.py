"""Protocol Sage Partner — meaning, mattering, personalized direction.

Partnership with you: co-goals, joint beneficence, real people, living
direction that updates after every sit and commit. You own decisions.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..hive.cell import create_cell
from ..mission import MISSION_ONE_LINER, evaluate_joint_beneficence

DEFAULT_SAGE_ROOT = Path(__file__).resolve().parents[2] / "sessions" / "sage"
DEFAULT_PROFILE_ID = "default"

SAGE_ROLE_BLURB = (
    "Personal sage partner — meaning, mattering, and personalized direction "
    "in partnership with you. Co-goals, joint beneficence, and real people. "
    "You own every decision; the partner shows your direction clearly."
)

REFUSALS = [
    "No romantic or parasocial 'I love you' product behavior.",
    "No 'you don't need other people' framing.",
    "No ego-only goals without shared/third good (joint beneficence fails).",
    "Human owns consequential decisions; sage does not live your life for you.",
]


@dataclass
class PersonStub:
    """Mattering stub — real humans only (not AI 'friends')."""

    name: str
    relation: str
    i_need_them_for: str = ""
    they_may_need_me_for: str = ""
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Commitment:
    text: str
    toward_person: str  # real other or "shared_good"
    due: str = ""
    created_at: float = field(default_factory=time.time)
    done: bool = False
    id: str = field(default_factory=lambda: f"c-{uuid.uuid4().hex[:8]}")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Reflection:
    """Human answer that shapes direction (from sit prompts or free note)."""

    text: str
    sit_id: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SageProfile:
    profile_id: str
    values_note: str = "contribution and mattering over status display"
    orientation: str = "beyond isolated ego — purpose with partners in a small hive"
    people: List[PersonStub] = field(default_factory=list)
    commitments: List[Commitment] = field(default_factory=list)
    reflections: List[Reflection] = field(default_factory=list)
    sit_log: List[Dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    mission: str = MISSION_ONE_LINER
    sage_role: str = SAGE_ROLE_BLURB
    refusals: List[str] = field(default_factory=lambda: list(REFUSALS))

    def root(self, base: Optional[Path] = None) -> Path:
        base = Path(base or DEFAULT_SAGE_ROOT)
        return base / self.profile_id

    def path(self, base: Optional[Path] = None) -> Path:
        return self.root(base) / "profile.json"

    def save(self, base: Optional[Path] = None) -> Path:
        root = self.root(base)
        root.mkdir(parents=True, exist_ok=True)
        path = self.path(base)
        data = {
            "profile_id": self.profile_id,
            "values_note": self.values_note,
            "orientation": self.orientation,
            "people": [p.to_dict() for p in self.people],
            "commitments": [c.to_dict() for c in self.commitments],
            "reflections": [r.to_dict() for r in self.reflections],
            "sit_log": self.sit_log,
            "created_at": self.created_at,
            "mission": self.mission,
            "sage_role": self.sage_role,
            "refusals": self.refusals,
            "updated_at": time.time(),
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path

    def add_person(self, person: PersonStub, *, base: Optional[Path] = None) -> Path:
        # update if same name
        for i, existing in enumerate(self.people):
            if existing.name.lower() == person.name.lower():
                self.people[i] = PersonStub(
                    name=person.name,
                    relation=person.relation or existing.relation,
                    i_need_them_for=person.i_need_them_for or existing.i_need_them_for,
                    they_may_need_me_for=person.they_may_need_me_for or existing.they_may_need_me_for,
                    notes=person.notes or existing.notes,
                )
                return self.write_direction(base=base)
        self.people.append(person)
        return self.write_direction(base=base)

    def add_commitment(self, commitment: Commitment, *, base: Optional[Path] = None) -> Path:
        self.commitments.append(commitment)
        return self.write_direction(base=base)

    def complete_commitment(
        self,
        *,
        match: str,
        base: Optional[Path] = None,
    ) -> Optional[Commitment]:
        """Mark first open commitment matching text or id as done; refresh direction."""
        m = match.strip().lower()
        for c in self.commitments:
            if c.done:
                continue
            if c.id == match or m in c.text.lower() or m == c.toward_person.lower():
                c.done = True
                self.write_direction(base=base)
                return c
        return None

    def add_reflection(
        self,
        text: str,
        *,
        sit_id: str = "",
        base: Optional[Path] = None,
    ) -> Path:
        self.reflections.append(Reflection(text=text.strip(), sit_id=sit_id))
        return self.write_direction(base=base)

    def build_direction(self) -> Dict[str, Any]:
        """Synthesize a *personalized* direction card from this profile only."""
        return synthesize_direction(self)

    def write_direction(self, base: Optional[Path] = None) -> Path:
        """Write direction.json + direction.md under the profile root."""
        self.sage_role = SAGE_ROLE_BLURB
        self.refusals = list(REFUSALS)
        direction = self.build_direction()
        root = self.root(base)
        root.mkdir(parents=True, exist_ok=True)
        jpath = root / "direction.json"
        mpath = root / "direction.md"
        jpath.write_text(json.dumps(direction, indent=2), encoding="utf-8")
        mpath.write_text(render_direction_markdown(direction), encoding="utf-8")
        self.save(base)
        return mpath

    def export_pack(self, base: Optional[Path] = None) -> Path:
        """Write a shareable pack: direction + people + open commits + recent sits."""
        self.write_direction(base=base)
        root = self.root(base)
        pack_dir = root / "export"
        pack_dir.mkdir(parents=True, exist_ok=True)
        direction = self.build_direction()
        sits = [s for s in self.sit_log if s.get("sit_id")][-10:]
        pack = {
            "profile_id": self.profile_id,
            "exported_at": time.time(),
            "values": self.values_note,
            "orientation": self.orientation,
            "direction": direction,
            "people": [p.to_dict() for p in self.people],
            "commitments_open": [c.to_dict() for c in self.commitments if not c.done],
            "recent_sits": sits,
            "partner_role": self.sage_role,
        }
        (pack_dir / "pack.json").write_text(json.dumps(pack, indent=2), encoding="utf-8")
        md = render_export_markdown(pack)
        md_path = pack_dir / "pack.md"
        md_path.write_text(md, encoding="utf-8")
        # copy latest direction into export for one-folder share
        dmd = root / "direction.md"
        if dmd.exists():
            (pack_dir / "direction.md").write_text(dmd.read_text(encoding="utf-8"), encoding="utf-8")
        return md_path

    def sit(
        self,
        situation: str,
        *,
        co_goal: str,
        human_effect: str = "advanced",
        ai_effect: str = "neutral",
        shared_effect: str = "advanced",
        mode: str = "default",
        notes: str = "",
        reflection: str = "",
        base: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Open a partnership turn: hive cell + beneficence + counsel + refresh direction."""
        cell = create_cell(
            co_goal,
            orientation=self.orientation,
            human_name="human",
            human_responsibility="life ownership, values, real relationships, final decisions",
            human_needed_for="meaning and accountability — your role in the partnership",
            ai_name="sage_partner",
            ai_responsibility=SAGE_ROLE_BLURB,
            ai_needed_for="structure, direction, options in partnership with you",
        )
        result = cell.set_beneficence(
            human=human_effect,
            ai_partner=ai_effect,
            shared_or_third=shared_effect,
            mode=mode,
            notes=notes or situation[:200],
        )
        cell.log_contribution("human", "brought situation", situation[:500])
        cell.log_contribution("ai", "sage partner turn", "structure + beneficence + direction")

        counsel = _frankl_shaped_prompts(situation, co_goal, self.people)
        cell_path = cell.save(root=(self.root(base) / "cells"))
        sit_id = f"sit-{uuid.uuid4().hex[:10]}"
        entry = {
            "ts": time.time(),
            "sit_id": sit_id,
            "situation": situation,
            "co_goal": co_goal,
            "beneficence": result.to_dict(),
            "counsel_prompts": counsel,
            "cell_id": cell.cell_id,
            "cell_path": str(cell_path),
            "ok": result.ok,
        }
        if reflection.strip():
            entry["reflection"] = reflection.strip()
            self.reflections.append(Reflection(text=reflection.strip(), sit_id=sit_id))
        self.sit_log.append(entry)
        direction_path = self.write_direction(base=base)
        entry["direction_path"] = str(direction_path)
        entry["direction"] = self.build_direction()
        self.save(base)
        return entry


def _frankl_shaped_prompts(
    situation: str,
    co_goal: str,
    people: List[PersonStub],
) -> List[str]:
    """Real structured questions (not LLM). Creative / experiential / attitudinal."""
    names = ", ".join(p.name for p in people[:5]) or "(none listed yet — consider who is real in your life)"
    return [
        f"Creative: What concrete work or deed does co-goal '{co_goal}' ask of you this week?",
        f"Experiential: Whom might you encounter or care for in this (people on file: {names})?",
        "Attitudinal: If part of this cannot be fixed, what stance keeps dignity without ego display?",
        "Mattering: Who would notice if you followed through — or if you disappeared from this?",
        "Selfless check: Does this mainly inflate status, or serve a good beyond your image?",
        f"Situation held: {situation[:240]}",
    ]


def synthesize_direction(profile: SageProfile) -> Dict[str, Any]:
    """Build personalized direction from profile data only (deterministic, no LLM required)."""
    sits = [s for s in profile.sit_log if s.get("sit_id") or s.get("co_goal")]
    passed = [s for s in sits if s.get("ok") is True]
    failed = [s for s in sits if s.get("ok") is False]
    open_c = [c for c in profile.commitments if not c.done]
    done_c = [c for c in profile.commitments if c.done]
    reflections = [r.text for r in profile.reflections[-5:]]

    # Who the direction points toward (mattering graph)
    toward: List[Dict[str, str]] = []
    for p in profile.people:
        toward.append(
            {
                "name": p.name,
                "relation": p.relation,
                "they_may_need_you": p.they_may_need_me_for or "(name how they need you)",
                "you_may_need_them": p.i_need_them_for or "(name how you need them)",
            }
        )

    # Active purpose threads = unique passed co-goals (recent first)
    threads: List[str] = []
    for s in reversed(passed):
        g = (s.get("co_goal") or "").strip()
        if g and g not in threads:
            threads.append(g)
        if len(threads) >= 5:
            break

    situations = []
    for s in reversed(passed):
        sit = (s.get("situation") or "").strip()
        if sit and sit not in situations:
            situations.append(sit)
        if len(situations) >= 3:
            break

    next_acts = [f"{c.text} → {c.toward_person}" + (f" (due {c.due})" if c.due else "") for c in open_c[:8]]

    # Suggested moves from threads when commits empty (still personal)
    suggested: List[str] = []
    if threads and toward:
        primary = toward[0]["name"]
        suggested.append(f"Take one concrete step this week on: {threads[0]} (with {primary} in mind)")
        if len(toward) > 1:
            suggested.append(f"Name how {toward[1]['name']} fits this direction — or protect time for them")
    elif threads:
        suggested.append(f"Take one concrete step this week on: {threads[0]}")
        suggested.append("Add one real person this direction serves or is held with")
    elif toward:
        suggested.append(f"Form a co-goal that serves {toward[0]['name']} and your values")
    for p in profile.people:
        if p.they_may_need_me_for and not any(p.name in a for a in next_acts):
            suggested.append(f"Act on what {p.name} may need: {p.they_may_need_me_for}")

    # North star sentence from *their* data
    if threads and toward:
        names = ", ".join(t["name"] for t in toward[:3])
        north = (
            f"Given your values ({profile.values_note}), your direction is: "
            f"{threads[0]} — held with {names}."
        )
    elif threads:
        north = (
            f"Given your values ({profile.values_note}), your direction is: {threads[0]}."
        )
    elif toward:
        names = ", ".join(t["name"] for t in toward[:3])
        north = (
            f"Your people are {names}. Your next direction is a co-goal that serves them "
            f"under values: {profile.values_note}."
        )
    else:
        north = (
            f"Your orientation: {profile.orientation}. "
            "Add people and a co-goal so your personal direction can lock in."
        )
    if reflections:
        north += f" You said: “{reflections[-1][:180]}”"

    if failed and not passed:
        pattern = "Sits are failing joint beneficence — shift from ego-only aims toward shared good."
    elif failed and passed:
        pattern = (
            f"{len(passed)} aligned sit(s); {len(failed)} redirected. "
            "Keep the passed threads; treat fails as course-correction."
        )
    elif passed:
        pattern = f"{len(passed)} aligned sit(s) — this is your living direction; act on it."
    else:
        pattern = "Begin with one sit and one person — direction emerges from your own record."

    deepen: List[str] = []
    if not profile.people:
        deepen.append("Add at least one real human to your mattering map.")
    if not open_c:
        deepen.append("Bind one commitment so direction becomes action.")
    if not threads:
        deepen.append("Pass one co-goal through joint beneficence.")
    for p in profile.people:
        if not p.they_may_need_me_for:
            deepen.append(f"Name how {p.name} may need you.")
        if not p.i_need_them_for:
            deepen.append(f"Name how you need {p.name} (mutual mattering).")

    return {
        "profile_id": profile.profile_id,
        "generated_at": time.time(),
        "mission": profile.mission,
        "values": profile.values_note,
        "orientation": profile.orientation,
        "north_star": north,
        "pattern": pattern,
        "mattering": toward,
        "purpose_threads": threads,
        "situations_held": situations,
        "next_acts": next_acts,
        "suggested_moves": suggested[:8],
        "deepen": deepen[:12],
        "reflections": reflections,
        "completed_recently": [f"{c.text} → {c.toward_person}" for c in done_c[-5:]],
        "stats": {
            "people": len(profile.people),
            "sits_passed": len(passed),
            "sits_failed": len(failed),
            "commitments_open": len(open_c),
            "commitments_done": len(done_c),
        },
        "partner_role": profile.sage_role or SAGE_ROLE_BLURB,
    }


def render_direction_markdown(d: Dict[str, Any]) -> str:
    """Human-readable personalized direction (showable)."""
    lines = [
        f"# Personal direction — {d.get('profile_id', 'sage')}",
        "",
        "## North star",
        "",
        d.get("north_star", ""),
        "",
        f"**Values:** {d.get('values', '')}",
        f"**Orientation:** {d.get('orientation', '')}",
        "",
        f"**Pattern:** {d.get('pattern', '')}",
        "",
        "## Who you matter with",
        "",
    ]
    mattering = d.get("mattering") or []
    if not mattering:
        lines.append("*Add people — direction is personal when it names who.*")
    else:
        for m in mattering:
            lines.append(
                f"- **{m['name']}** ({m['relation']}): "
                f"they may need you for *{m['they_may_need_you']}*; "
                f"you may need them for *{m['you_may_need_them']}*"
            )
    lines.extend(["", "## Purpose threads", ""])
    threads = d.get("purpose_threads") or []
    if not threads:
        lines.append("*Sit with a co-goal that serves shared good.*")
    else:
        for t in threads:
            lines.append(f"- {t}")
    lines.extend(["", "## Your next acts", ""])
    acts = d.get("next_acts") or []
    if acts:
        for a in acts:
            lines.append(f"- [ ] {a}")
    else:
        for s in d.get("suggested_moves") or []:
            lines.append(f"- [ ] {s}")
    if acts and d.get("suggested_moves"):
        lines.extend(["", "## Also suggested", ""])
        for s in d.get("suggested_moves") or []:
            lines.append(f"- {s}")
    refs = d.get("reflections") or []
    if refs:
        lines.extend(["", "## Your words (shaping direction)", ""])
        for r in refs:
            lines.append(f"> {r}")
    done = d.get("completed_recently") or []
    if done:
        lines.extend(["", "## Completed", ""])
        for x in done:
            lines.append(f"- [x] {x}")
    lines.extend(["", "## Deepen", ""])
    deepen = d.get("deepen") or []
    if not deepen:
        lines.append("- Direction is actionable — live the next act, then sit again.")
    else:
        for g in deepen:
            lines.append(f"- {g}")
    stats = d.get("stats") or {}
    lines.extend(
        [
            "",
            "## Snapshot",
            "",
            f"- People: {stats.get('people', 0)}",
            f"- Sits aligned / redirected: {stats.get('sits_passed', 0)} / {stats.get('sits_failed', 0)}",
            f"- Commitments open / done: {stats.get('commitments_open', 0)} / {stats.get('commitments_done', 0)}",
            "",
            "---",
            "",
            f"*{d.get('partner_role', '')}*",
            "",
            "This is your direction. The sage partner walks it with you.",
            "",
        ]
    )
    return "\n".join(lines)


def render_export_markdown(pack: Dict[str, Any]) -> str:
    """Pack for showing a person (friend, counselor, self) — personalized."""
    d = pack.get("direction") or {}
    lines = [
        f"# Sage partner export — {pack.get('profile_id')}",
        "",
        f"Exported for sharing a clear personal direction.",
        "",
        render_direction_markdown(d),
        "",
        "## Recent partnership sits",
        "",
    ]
    for s in pack.get("recent_sits") or []:
        flag = "aligned" if s.get("ok") else "redirected"
        lines.append(f"- ({flag}) {s.get('situation', '')[:80]} → **{s.get('co_goal', '')}**")
    lines.extend(["", "## Open commitments", ""])
    for c in pack.get("commitments_open") or []:
        lines.append(f"- {c.get('text')} → {c.get('toward_person')}")
    lines.append("")
    return "\n".join(lines)


def load_or_create_profile(
    profile_id: str = DEFAULT_PROFILE_ID,
    *,
    base: Optional[Path] = None,
    values_note: Optional[str] = None,
    orientation: Optional[str] = None,
) -> SageProfile:
    base = Path(base or DEFAULT_SAGE_ROOT)
    path = base / profile_id / "profile.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        people = [PersonStub(**p) for p in data.get("people", [])]
        commits = []
        for c in data.get("commitments", []):
            commits.append(
                Commitment(
                    text=c["text"],
                    toward_person=c.get("toward_person", "shared_good"),
                    due=c.get("due", ""),
                    created_at=float(c.get("created_at") or time.time()),
                    done=bool(c.get("done", False)),
                    id=c.get("id") or f"c-{uuid.uuid4().hex[:8]}",
                )
            )
        reflections = [
            Reflection(
                text=r["text"],
                sit_id=r.get("sit_id", ""),
                created_at=float(r.get("created_at") or time.time()),
            )
            for r in data.get("reflections", [])
        ]
        return SageProfile(
            profile_id=data.get("profile_id", profile_id),
            values_note=data.get("values_note", ""),
            orientation=data.get("orientation", ""),
            people=people,
            commitments=commits,
            reflections=reflections,
            sit_log=list(data.get("sit_log", [])),
            created_at=float(data.get("created_at") or time.time()),
            mission=data.get("mission", MISSION_ONE_LINER),
            sage_role=data.get("sage_role", SAGE_ROLE_BLURB),
            refusals=list(data.get("refusals") or REFUSALS),
        )
    prof = SageProfile(profile_id=profile_id)
    if values_note:
        prof.values_note = values_note
    if orientation:
        prof.orientation = orientation
    prof.save(base)
    return prof
