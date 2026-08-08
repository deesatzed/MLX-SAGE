"""Partner app phase logic — automation without launching full Textual."""

from __future__ import annotations

from pathlib import Path

from nex.sage.partner import load_or_create_profile
from nex.sage.app import Phase, PartnerApp


def test_profile_auto_created(tmp_path: Path, monkeypatch):
    import nex.sage.partner as partner
    import nex.sage.app as appmod

    monkeypatch.setattr(partner, "DEFAULT_SAGE_ROOT", tmp_path)

    class FakeLocal:
        complete = True
        label = "m"
        path = str(tmp_path / "model")

    monkeypatch.setattr(appmod, "pick_default_local", lambda: FakeLocal())

    # Don't run full app — just construct and check helpers
    a = PartnerApp.__new__(PartnerApp)
    a.profile_id = "p1"
    a.model_path = None
    a.profile = load_or_create_profile("p1", base=tmp_path)
    a.dialog = None
    a.phase = Phase.BOOT
    a._busy = False
    a._transcript = []
    a._pending_person_name = ""

    assert a._profile_needs_person() is True
    assert a._model_ready_path() == FakeLocal.path

    # Simulate person step
    a.profile.add_person(
        __import__("nex.sage.partner", fromlist=["PersonStub"]).PersonStub(
            name="Sam", relation="friend"
        )
    )
    assert a._profile_needs_person() is False
    assert a._profile_needs_commit() is True
