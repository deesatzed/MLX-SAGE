"""Home + interactive setup + capture (real FS, injected prompts)."""

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
    run_interactive_setup,
)
from nex.sage.partner import load_or_create_profile
from nex.wattos import WattOSReport, render_wattos_text
from nex.propellant import PropellantLedger


def test_home_is_short_not_command_manual(tmp_path: Path, monkeypatch):
    import nex.sage.home as home

    monkeypatch.setattr(home, "pick_default_local", lambda: None)
    snap = build_home_snapshot("uxuser", base=tmp_path)
    text = render_home_text(snap)
    assert "MLX-SAGE" in text
    assert LABEL_PARTNER in text
    # Must NOT dump the old awful cookbook
    assert "nex sage people add" not in text
    assert "nex sage commit" not in text
    assert "Profile file:" not in text
    assert "talk" in text.lower()
    assert "setup" in text.lower()
    assert snap.needs_setup is True


def test_interactive_setup_adds_person_and_commit(tmp_path: Path, monkeypatch):
    import nex.sage.home as home

    class FakeLocal:
        complete = True
        label = "fake-ready"
        path = "/tmp/fake-model"

    monkeypatch.setattr(home, "pick_default_local", lambda: FakeLocal())

    answers = iter(["Alex", "friend", "check-in", "community", "Text Alex Sunday", "Alex"])
    confirms = iter([True, True, False])  # person, commit, no tui

    def ask(prompt, default=""):
        try:
            return next(answers)
        except StopIteration:
            return default

    def confirm(prompt, default=True):
        try:
            return next(confirms)
        except StopIteration:
            return default

    printed: list[str] = []

    result = run_interactive_setup(
        "setupuser",
        base=tmp_path,
        ask=ask,
        confirm=confirm,
        emit=printed.append,
        launch_tui=True,
    )
    assert result["person_added"] == "Alex"
    assert result["commit_added"] == "Text Alex Sunday"
    assert result["launch_tui"] is False
    prof = load_or_create_profile("setupuser", base=tmp_path)
    assert any(p.name == "Alex" for p in prof.people)
    assert any("Alex" in c.toward_person for c in prof.commitments if not c.done)


def test_capture_commit_person_reflect(tmp_path: Path):
    prof = load_or_create_profile("cap", base=tmp_path)
    r = parse_and_apply_capture(
        "/commit Call Alex weekly | Alex | Friday",
        prof,
        base=tmp_path,
    )
    assert r is not None and r.ok and r.kind == "commit"
    r2 = parse_and_apply_capture(
        "/person Alex | neighbor | check-in | community",
        prof,
        base=tmp_path,
    )
    assert r2 is not None and r2.ok
    r3 = parse_and_apply_capture("/reflect I want to show up", prof, base=tmp_path)
    assert r3 is not None and r3.ok
    assert parse_and_apply_capture("hello", prof, base=tmp_path) is None


def test_open_ritual_compact(tmp_path: Path, monkeypatch):
    import nex.sage.home as home

    monkeypatch.setattr(home, "pick_default_local", lambda: None)
    snap = build_home_snapshot("open", base=tmp_path)
    md = render_open_ritual_markdown(snap)
    assert "welcome" in md.lower()
    assert "/commit" in md or "/person" in md


def test_coach_text_not_cli_dump(tmp_path: Path, monkeypatch):
    import nex.sage.home as home

    monkeypatch.setattr(home, "pick_default_local", lambda: None)
    snap = build_home_snapshot("c", base=tmp_path)
    t = render_coach_text(snap)
    assert "nex sage people add --profile" not in t


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


def test_role_blurb_short():
    assert "Partner" in ROLE_BLURB
    assert "Rails" in ROLE_BLURB
