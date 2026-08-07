"""Native agent end report unifies WattOS with real oversight counters (no mocks)."""

from __future__ import annotations

from nex.agent import _print_agent_wattos
from nex.engine import SessionOversight
from nex.propellant import PropellantLedger
from nex.wattos import WattOSReport, render_wattos_text


def test_agent_wattos_local_tokens_when_present():
    o = SessionOversight()
    o.local_generation_tokens = 120
    o.avg_generation_tps = 41.5
    o.wall_time_s = 3.2
    o.policy_decisions = 4
    o.blocks = 0
    o.reviews = 1
    o.grok_escalations = 0
    o.note = "unit"
    # Build the same shape as _print_agent_wattos without printing
    ledger = PropellantLedger(max_burns=0, used=0, denied=0)
    report = WattOSReport(
        mode="agent",
        agent="nex-agent:test",
        wall_time_s=o.wall_time_s,
        policy_decisions=o.policy_decisions,
        blocks=o.blocks,
        reviews=o.reviews,
        grok_escalations=o.grok_escalations,
        propellant=ledger,
        local_generation_tokens=o.local_generation_tokens,
        avg_generation_tps=o.avg_generation_tps,
        note=o.note,
        grok_status="disabled (local agent)",
    )
    text = render_wattos_text(report)
    assert "120" in text
    assert "41.5" in text
    assert "disabled (local agent)" in text
    assert "n/a" not in text.split("local gen tokens:")[1].split("\n")[0]


def test_print_agent_wattos_callable():
    o = SessionOversight()
    o.wall_time_s = 1.0
    o.local_generation_tokens = 10
    o.avg_generation_tps = 5.0
    _print_agent_wattos(o, "sid-test", "agent", use_grok_loop=False)
