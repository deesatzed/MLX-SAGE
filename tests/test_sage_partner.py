"""Protocol Sage — real profile + sit + beneficence, no mocks."""
from pathlib import Path

from nex.sage.partner import Commitment, PersonStub, load_or_create_profile


def test_profile_create_add_person_sit_pass(tmp_path: Path):
    p = load_or_create_profile("testuser", base=tmp_path)
    p.add_person(
        PersonStub(
            name="Alex",
            relation="neighbor",
            they_may_need_me_for="weekly check-in",
            i_need_them_for="local community",
        )
    )
    p.save(tmp_path)
    entry = p.sit(
        "Feeling empty after work automation took my tasks",
        co_goal="Establish two real check-ins with Alex this month",
        human_effect="advanced",
        ai_effect="neutral",
        shared_effect="advanced",
        notes="mattering over status",
        base=tmp_path,
    )
    assert entry["ok"] is True
    assert len(entry["counsel_prompts"]) >= 4
    assert (tmp_path / "testuser" / "profile.json").exists()
    assert "Alex" in (tmp_path / "testuser" / "profile.json").read_text()


def test_sit_ego_goal_fails_beneficence(tmp_path: Path):
    p = load_or_create_profile("ego", base=tmp_path)
    entry = p.sit(
        "Want clout",
        co_goal="Go viral for personal brand only",
        human_effect="advanced",
        ai_effect="advanced",
        shared_effect="neutral",
        base=tmp_path,
    )
    assert entry["ok"] is False


def test_commitment_persists(tmp_path: Path):
    p = load_or_create_profile("c1", base=tmp_path)
    p.add_commitment(Commitment(text="Call mom Sunday", toward_person="Mom"))
    p.save(tmp_path)
    p2 = load_or_create_profile("c1", base=tmp_path)
    assert len(p2.commitments) == 1
    assert p2.commitments[0].text.startswith("Call")


def test_personalized_direction_uses_profile_data(tmp_path: Path):
    p = load_or_create_profile("dir1", base=tmp_path)
    p.add_person(
        PersonStub(
            name="Jordan",
            relation="friend",
            they_may_need_me_for="rides to clinic",
            i_need_them_for="honest talk",
        )
    )
    entry = p.sit(
        "Lonely after job change",
        co_goal="Be present for Jordan's clinic weeks",
        human_effect="advanced",
        ai_effect="neutral",
        shared_effect="advanced",
        base=tmp_path,
    )
    assert entry.get("direction_path")
    assert "Jordan" in entry["direction"]["north_star"]
    p.add_commitment(
        Commitment(text="Drive Jordan Tuesday", toward_person="Jordan"),
        base=tmp_path,
    )
    d = p.build_direction()
    assert "Jordan" in d["north_star"]
    assert any("clinic" in t.lower() or "Jordan" in t for t in d["purpose_threads"])
    assert any("Drive Jordan" in a for a in d["next_acts"])
    md_path = tmp_path / "dir1" / "direction.md"
    assert md_path.exists()
    text = md_path.read_text(encoding="utf-8")
    assert "Jordan" in text
    assert "Drive Jordan" in text


def test_export_pack_contains_direction(tmp_path: Path):
    p = load_or_create_profile("ex1", base=tmp_path)
    p.add_person(PersonStub(name="Lee", relation="parent", they_may_need_me_for="visits"), base=tmp_path)
    p.sit(
        "Want purpose",
        co_goal="Weekly visit with Lee",
        human_effect="advanced",
        ai_effect="neutral",
        shared_effect="advanced",
        base=tmp_path,
    )
    pack_md = p.export_pack(base=tmp_path)
    assert pack_md.exists()
    body = pack_md.read_text(encoding="utf-8")
    assert "Lee" in body
    assert (tmp_path / "ex1" / "export" / "pack.json").exists()


def test_reflect_and_done_shape_direction(tmp_path: Path):
    p = load_or_create_profile("rd1", base=tmp_path)
    p.add_person(
        PersonStub(name="Pat", relation="friend", they_may_need_me_for="listening"),
        base=tmp_path,
    )
    p.sit(
        "Scattered",
        co_goal="Be a steady friend to Pat",
        human_effect="advanced",
        ai_effect="neutral",
        shared_effect="advanced",
        reflection="I will show up weekly without performing",
        base=tmp_path,
    )
    p.add_commitment(Commitment(text="Text Pat Friday", toward_person="Pat"), base=tmp_path)
    done = p.complete_commitment(match="Text Pat", base=tmp_path)
    assert done is not None and done.done is True
    d = p.build_direction()
    assert "show up weekly" in d["north_star"].lower() or any("show up" in r.lower() for r in d.get("reflections", []))
    assert any("Text Pat" in x for x in d.get("completed_recently", []))
