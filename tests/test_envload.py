"""envload — real file parse, no secret logging."""

from __future__ import annotations

import os
from pathlib import Path

from nex.envload import load_dotenv


def test_load_dotenv_sets_missing_keys(tmp_path: Path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("UNIT_TEST_FOO=bar\n# comment\nexport UNIT_TEST_BAZ=qux\n", encoding="utf-8")
    monkeypatch.delenv("UNIT_TEST_FOO", raising=False)
    monkeypatch.delenv("UNIT_TEST_BAZ", raising=False)
    assert load_dotenv(env_file, override=False) is True
    assert os.environ.get("UNIT_TEST_FOO") == "bar"
    assert os.environ.get("UNIT_TEST_BAZ") == "qux"


def test_load_dotenv_does_not_override_existing(tmp_path: Path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("UNIT_TEST_KEEP=fromfile\n", encoding="utf-8")
    monkeypatch.setenv("UNIT_TEST_KEEP", "fromshell")
    assert load_dotenv(env_file, override=False) is True
    assert os.environ.get("UNIT_TEST_KEEP") == "fromshell"
