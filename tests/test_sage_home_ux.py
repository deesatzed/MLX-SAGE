"""UX Recs 1–5 — home, coach, capture, open ritual, role labels (real FS)."""

from __future__ import annotations

from pathlib import Path

from nex.sage.home import (
    LABEL_PARTNER,
    LABEL_RAILS,
    ROLE_BLURB,
    build_home_snapshot,
    parse_and_apply_capture,
    render_coach_text,
    render_home_text,
    render_open_ritual_markdown,
)
from nex.sage.partner import load_or_create_profile
from nex.wattos import WattOSReport, render_wattos_text
from nex.propellant import PropellantLedger


def test_home_snapshot_empty_profile_needs_coach(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "")
    # isolate default sage root
    import nex.sage.partner as partner
    import nex.sage.home as home

    monkeypatch.setattr(partner, "DEFAULT_SAGE_ROOT", tmp_path / "sage")
    monkeypatch.setattr(home, "pick_default_local", lambda: None)

    snap = build_home_snapshot("uxuser", base=tmp_path / "sage")
    assert snap.profile_id == "uxuser"
    assert snap.needs_coach is True
    assert snap.people_count == 0
    text = render_home_text(snap)
    assert "Partnership home" in text
    assert LABEL_PARTNER in text
    assert LABEL_RAILS in text or "Rails" in text
    assert "nex sage tui" in text
    coach = render_coach_text(snap)
    assert "First-run coach" in coach
    assert "supervise" not in coach.lower() or "will not tour" in coach.lower()
    assert "nex sage tui" in coach


def test_capture_commit_person_reflect(tmp_path: Path):
    prof = load_or_create_profile("cap", base=tmp_path)
    r = parse_and_apply_capture(
        "/commit Call Alex weekly | Alex | Friday",
        prof,
        base=tmp_path,
    )
    assert r is not None and r.ok and r.kind == "commit"
    assert any(not c.done and "Alex" in c.toward_person for c in prof.commitments)

    r2 = parse_and_apply_capture(
        "/person Alex | neighbor | check-in | community",
        prof,
        base=tmp_path,
    )
    assert r2 is not None and r2.ok
    assert any(p.name == "Alex" for p in prof.people)

    r3 = parse_and_apply_capture("/reflect I want to show up for neighbors", prof, base=tmp_path)
    assert r3 is not None and r3.ok and r3.updated_direction

    r4 = parse_and_apply_capture("hello normal chat", prof, base=tmp_path)
    assert r4 is None


def test_open_ritual_markdown_has_partner_label(tmp_path: Path, monkeypatch):
    import nex.sage.home as home

    monkeypatch.setattr(home, "pick_default_local", lambda: None)
    snap = build_home_snapshot("open", base=tmp_path)
    md = render_open_ritual_markdown(snap)
    assert "Welcome back" in md
    assert LABEL_PARTNER in md or "Partner" in md
    assert "/commit" in md


def test_wattos_rails_label():
    text = render_wattos_text(
        WattOSReport(
            mode="agent",
            agent="t",
            wall_time_s=1.0,
            policy_decisions=1,
            blocks=0,
            reviews=0,
            grok_escalations=0,
            propellant=PropellantLedger(max_burns=0),
            local_generation_tokens=1,
            avg_generation_tps=1.0,
            note="n",
            grok_status="disabled",
        )
    )
    assert "Rails" in text
    assert "sage" in text.lower()


def test_role_blurb_mentions_both_modes():
    assert "Partner" in ROLE_BLURB
    assert "Rails" in ROLE_BLURB
    assert "Grok" in ROLE_BLURB
