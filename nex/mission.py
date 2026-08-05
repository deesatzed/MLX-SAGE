"""Mission constitution + joint beneficence (destination v4).

Source: docs/sessions/2026-08-04-destination-anti-disposability-brainstorm.md
Not a claim that we install existential meaning or machine consciousness.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


MISSION_ONE_LINER = (
    "As AI grows more capable, foster human–AI partnership and healthy hives "
    "so humans find purpose and meaning with AI—as needed members of shared "
    "purpose beyond the isolated ego."
)

MISSION_CONSTITUTION = """
DESTINATION
As AI grows more capable, foster human–AI partnership and healthy
hives so humans find purpose and meaning with AI—as needed members
of shared purpose beyond the isolated ego.

STANCE
AI progression continues. Partnership, not war and not worship.
Hive = multi-mind with roles and mutual need—not erase-the-person swarm.
“More sentient” = design horizon for co-goals, memory, negotiation;
not a claim that current models are conscious.
Inner: meaning ∥ contentment ∥ selfless/other-oriented more than ego status.
Ego keeps boundaries; self-transcendence aims the life.
Joint beneficence: outcomes should advance all parties—human(s),
AI partner(s), and the shared or third-party good.

ENEMY
Human-as-optional; master/slave; fake intimacy; ego-status machines;
metric-only worth; faceless swarms; purposeless leftover life; consolation hype.

WE NEVER
Stop AI as brand; simulate cherishing for engagement; dissolve persons
into the hive; feed pure ego comparison as “purpose”; claim we install
meaning or proven machine consciousness; invent needs for existing code.
""".strip()


class PartyEffect(str, Enum):
    """Effect of a proposed hive action on one party."""

    ADVANCED = "advanced"
    NEUTRAL = "neutral"
    HARMED = "harmed"


@dataclass(frozen=True)
class JointBeneficenceResult:
    ok: bool
    mode: str  # "strict" | "default"
    human: PartyEffect
    ai_partner: PartyEffect
    shared_or_third: PartyEffect
    reasons: List[str]
    summary: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "mode": self.mode,
            "human": self.human.value,
            "ai_partner": self.ai_partner.value,
            "shared_or_third": self.shared_or_third.value,
            "reasons": list(self.reasons),
            "summary": self.summary,
        }


def _parse_effect(value: str | PartyEffect) -> PartyEffect:
    if isinstance(value, PartyEffect):
        return value
    v = str(value).strip().lower()
    for e in PartyEffect:
        if e.value == v:
            return e
    raise ValueError(f"effect must be advanced|neutral|harmed, got {value!r}")


def evaluate_joint_beneficence(
    *,
    human: str | PartyEffect,
    ai_partner: str | PartyEffect,
    shared_or_third: str | PartyEffect,
    mode: str = "default",
    notes: Optional[str] = None,
) -> JointBeneficenceResult:
    """Evaluate whether a proposal advances all parties (joint beneficence).

    Parties:
      - human: the particular person(s) in the hive
      - ai_partner: complementary AI role (integrity, clear role—not fake feelings)
      - shared_or_third: shared mission good and/or identifiable third parties

    Modes:
      - strict: all three must be advanced
      - default: none harmed; human and shared at least advanced; AI at least neutral
        (AI may be neutral when honestly only assisting without new capability claim)
    """
    h = _parse_effect(human)
    a = _parse_effect(ai_partner)
    s = _parse_effect(shared_or_third)
    mode = (mode or "default").strip().lower()
    if mode not in ("strict", "default"):
        raise ValueError("mode must be strict|default")

    reasons: List[str] = []
    if notes:
        reasons.append(f"note: {notes}")

    if h == PartyEffect.HARMED:
        reasons.append("human is harmed — fails joint beneficence")
    if a == PartyEffect.HARMED:
        reasons.append("ai_partner is harmed (role integrity / honesty) — fails")
    if s == PartyEffect.HARMED:
        reasons.append("shared/third-party good is harmed — fails")

    if any(x == PartyEffect.HARMED for x in (h, a, s)):
        return JointBeneficenceResult(
            ok=False,
            mode=mode,
            human=h,
            ai_partner=a,
            shared_or_third=s,
            reasons=reasons,
            summary="REJECT: at least one party harmed",
        )

    if mode == "strict":
        ok = all(x == PartyEffect.ADVANCED for x in (h, a, s))
        if not ok:
            reasons.append("strict mode requires all three parties advanced")
        summary = (
            "PASS: all parties advanced (strict)"
            if ok
            else "REJECT: strict joint beneficence not met"
        )
        return JointBeneficenceResult(
            ok=ok, mode=mode, human=h, ai_partner=a, shared_or_third=s,
            reasons=reasons, summary=summary,
        )

    # default
    ok = (
        h == PartyEffect.ADVANCED
        and s == PartyEffect.ADVANCED
        and a in (PartyEffect.ADVANCED, PartyEffect.NEUTRAL)
    )
    if h != PartyEffect.ADVANCED:
        reasons.append("default mode requires human advanced")
    if s != PartyEffect.ADVANCED:
        reasons.append("default mode requires shared/third advanced")
    if a == PartyEffect.HARMED:
        reasons.append("ai_partner must not be harmed")
    if ok and a == PartyEffect.NEUTRAL:
        reasons.append("ai_partner neutral (honest assist) allowed in default mode")
    if ok and a == PartyEffect.ADVANCED:
        reasons.append("all parties advanced or AI neutral-assist")

    summary = (
        "PASS: joint beneficence (default)"
        if ok
        else "REJECT: joint beneficence (default) not met"
    )
    return JointBeneficenceResult(
        ok=ok, mode=mode, human=h, ai_partner=a, shared_or_third=s,
        reasons=reasons, summary=summary,
    )


def print_constitution(console=None) -> None:
    try:
        from rich.console import Console
        from rich.panel import Panel
        c = console or Console()
        c.print(Panel(MISSION_CONSTITUTION, title="Mission constitution", border_style="cyan"))
        c.print(f"[dim]{MISSION_ONE_LINER}[/dim]\n")
    except ImportError:
        print(MISSION_CONSTITUTION)
        print(MISSION_ONE_LINER)
