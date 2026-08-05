#!/usr/bin/env python3
"""
grok-claude — Claude Code under Superintendant (Sentinel + propellant Grok + WattOS).

Usage:
  python scripts/grok_claude.py .
  # or after install: grok-claude .
"""

from __future__ import annotations

import argparse
import os
import shlex
import sys
import tempfile
from pathlib import Path

try:
    from nex.superintend import run_supervised_session
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from nex.superintend import run_supervised_session


def main() -> int:
    parser = argparse.ArgumentParser(description="Run claude under Superintendant + WattOS")
    parser.add_argument("workspace", nargs="?", default=".", help="Workspace to run in")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--grok-in-loop",
        action="store_true",
        default=os.environ.get("GROK_IN_LOOP") == "true",
        help="Deprecated synonym for enabling Grok",
    )
    parser.add_argument("--grok", dest="use_grok", action="store_true", default=True)
    parser.add_argument("--no-grok", dest="use_grok", action="store_false")
    parser.add_argument("--max-grok", type=int, default=3)
    parser.add_argument(
        "--on-empty",
        default="human_or_block",
        choices=["human_or_block", "block", "allow_local_only"],
    )
    parser.add_argument("--wattos", dest="wattos", action="store_true", default=True)
    parser.add_argument("--no-wattos", dest="wattos", action="store_false")
    args = parser.parse_args()

    use_grok = bool(args.use_grok or args.grok_in_loop)

    if args.dry_run:
        print(
            "DRY RUN: Would run 'claude' under Superintendant "
            f"(max_grok={args.max_grok}, grok={use_grok}, wattos={args.wattos})."
        )
        return 0

    with tempfile.TemporaryDirectory(prefix="grok-claude-") as tmp:
        cwd = Path(tmp) / "workspace"
        cwd.mkdir()
        cmd = f"claude {shlex.quote(args.workspace)}"
        return run_supervised_session(
            cmd=cmd,
            workspace=str(cwd),
            agent_label="claude",
            max_grok=args.max_grok,
            use_grok=use_grok,
            on_empty=args.on_empty,
            wattos=args.wattos,
            trust_agent="claude",
        )


if __name__ == "__main__":
    raise SystemExit(main())
