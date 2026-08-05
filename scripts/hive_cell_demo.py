#!/usr/bin/env python3
"""Real Hive Cell demo — partnership + joint beneficence (no mocks).

Shows a purpose-shaped co-goal that passes, and an ego-status goal that fails.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nex.hive.cell import create_cell
from nex.mission import MISSION_ONE_LINER, print_constitution


def main() -> int:
    print("=== Hive Cell demo (purpose with partnership) ===\n")
    print(MISSION_ONE_LINER, "\n")
    print_constitution()

    good = create_cell(
        "Draft a one-page meds schedule a daughter can use when caring for her father",
        orientation="care for a particular elder — beyond ego display",
    )
    gr = good.set_beneficence(
        human="advanced",
        ai_partner="neutral",
        shared_or_third="advanced",
        notes="daughter gains clarity; father safety; AI only structures",
    )
    good.log_contribution("human", "knows father, owns medical judgment")
    good.log_contribution("ai", "formats schedule template")
    gpath = good.save()
    print(f"[PASS path] {gr.summary}")
    print(f"  receipt: {gpath}")
    assert gr.ok, gr

    bad = create_cell(
        "Maximize personal followers with synthetic hype",
        orientation="ego status",
    )
    br = bad.set_beneficence(
        human="advanced",
        ai_partner="advanced",
        shared_or_third="neutral",
        notes="no shared good — ego only",
    )
    print(f"[FAIL path] {br.summary}")
    assert not br.ok, br

    print("\n=== demo PASS: joint beneficence discriminates purpose vs ego ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
