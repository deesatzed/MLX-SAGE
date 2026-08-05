"""Hive cell — real FS session, no mocks."""
from pathlib import Path

from nex.hive.cell import create_cell


def test_create_cell_has_three_roles_and_saves(tmp_path: Path):
    cell = create_cell("Help neighbor document meds schedule for caregiver")
    assert cell.co_goal
    assert len(cell.roles) == 3
    parties = {r.party for r in cell.roles}
    assert parties == {"human", "ai", "shared"}

    r = cell.set_beneficence(
        human="advanced",
        ai_partner="neutral",
        shared_or_third="advanced",
        notes="caregiver gets clarity; AI drafts only",
    )
    assert r.ok is True

    cell.log_contribution("human", "set co-goal and values")
    cell.log_contribution("ai", "structured draft outline")
    path = cell.save(root=tmp_path)
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "joint beneficence" in text.lower() or "beneficence" in text
    assert cell.cell_id in text


def test_reject_ego_only_goal_beneficence():
    cell = create_cell("Go viral for personal brand")
    r = cell.set_beneficence(
        human="advanced",
        ai_partner="advanced",
        shared_or_third="neutral",  # no shared good
        mode="default",
    )
    assert r.ok is False
