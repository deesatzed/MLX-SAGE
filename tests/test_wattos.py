"""WattOS report honesty — no fake local tokens for child-agent wraps."""
from nex.propellant import PropellantLedger
from nex.wattos import WattOSReport, render_wattos_text


def test_child_agent_local_tokens_are_na_not_zero():
    rep = WattOSReport(
        mode="supervise",
        agent="claude",
        wall_time_s=1.5,
        policy_decisions=2,
        blocks=1,
        reviews=0,
        grok_escalations=0,
        propellant=PropellantLedger(max_burns=3),
        local_generation_tokens=None,  # not measured
        avg_generation_tps=None,
        note="test",
        grok_status="skipped (no key)",
    )
    text = render_wattos_text(rep)
    assert "n/a" in text.lower()
    assert "child agent" in text.lower() or "not local" in text.lower()
    # Must not claim measured zero tokens as efficiency
    compact = text.lower().replace(" ", "")
    assert "localgentokens:0" not in compact
    assert "localgentokens0" not in compact


def test_local_agent_shows_token_counts():
    rep = WattOSReport(
        mode="agent",
        agent="nex",
        wall_time_s=2.0,
        policy_decisions=1,
        blocks=0,
        reviews=1,
        grok_escalations=1,
        propellant=PropellantLedger(max_burns=3, used=1),
        local_generation_tokens=100,
        avg_generation_tps=40.0,
        note="local mlx",
        grok_status="ok",
    )
    text = render_wattos_text(rep)
    assert "100" in text
    assert "40" in text
    assert "1/3" in text or "propellant" in text.lower()


def test_propellant_denied_in_text():
    led = PropellantLedger(max_burns=0)
    led.burn()  # denied
    rep = WattOSReport(
        mode="supervise",
        agent="demo",
        wall_time_s=0.1,
        policy_decisions=1,
        blocks=0,
        reviews=1,
        grok_escalations=0,
        propellant=led,
        local_generation_tokens=None,
        avg_generation_tps=None,
        note="denied demo",
        grok_status="propellant empty",
    )
    text = render_wattos_text(rep)
    assert "denied" in text.lower() or str(led.denied) in text
