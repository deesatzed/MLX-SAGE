#!/usr/bin/env python3
"""Protocol Sage demo — real profile, pass/fail beneficence, commitment (no mocks)."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nex.sage.partner import Commitment, PersonStub, load_or_create_profile
from nex.mission import MISSION_ONE_LINER


def main() -> int:
    print("=== Protocol Sage Partner demo ===\n")
    print(MISSION_ONE_LINER, "\n")

    with tempfile.TemporaryDirectory(prefix="sage-demo-") as tmp:
        base = Path(tmp)
        p = load_or_create_profile("demo", base=base)
        p.add_person(
            PersonStub(
                name="Sam",
                relation="sibling",
                they_may_need_me_for="monthly call",
                i_need_them_for="family continuity",
            )
        )
        p.save(base)

        good = p.sit(
            "Work feels empty; machines took the busywork",
            co_goal="Keep a monthly real conversation with Sam and one act of help",
            human_effect="advanced",
            ai_effect="neutral",
            shared_effect="advanced",
            notes="sibling mattering",
            base=base,
        )
        assert good["ok"], good
        print("[PASS]", good["beneficence"]["summary"])
        print("  prompts:", len(good["counsel_prompts"]))

        bad = p.sit(
            "Want status",
            co_goal="Personal brand virality only",
            human_effect="advanced",
            ai_effect="advanced",
            shared_effect="neutral",
            base=base,
        )
        assert not bad["ok"], bad
        print("[FAIL]", bad["beneficence"]["summary"])

        p.add_commitment(Commitment(text="Call Sam this Sunday", toward_person="Sam"))
        path = p.save(base)
        print(f"[commit] saved {path}")
        assert "Sam" in path.read_text()

    print("\n=== demo PASS ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
