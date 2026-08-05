#!/usr/bin/env python3
"""Real Superintendant + WattOS demo — no mock Grok, no real claude binary required.

Runs a controlled child process under PTY that touches a protected path (.env)
so Sentinel policy fires. Asserts WattOS honesty and propellant behavior.

Usage:
  PYTHONPATH=. python scripts/wattos_superintendant_demo.py
  PYTHONPATH=. python scripts/wattos_superintendant_demo.py --max-grok 0
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

# Dev path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nex.propellant import PropellantLedger
from nex.sentinel.enforcer import ContinuousEnforcer, FileEffectObserver
from nex.sentinel.policy import PolicyAction, SentinelPolicy
from nex.superintend import run_supervised_session
from nex.wattos import WattOSReport, render_wattos_text


def _assert_policy_block_on_env(workspace: Path) -> None:
    """Real FS observer + policy: writing .env must BLOCK."""
    observer = FileEffectObserver(str(workspace))
    observer.snapshot()
    (workspace / ".env").write_text("SECRET=1\n", encoding="utf-8")
    effects = observer.diff()
    assert effects, "observer must see create of .env"
    policy = SentinelPolicy()
    decision = policy.evaluate(effects)
    assert decision.action == PolicyAction.BLOCK, f"expected BLOCK, got {decision}"
    print(f"[demo] policy BLOCK on .env: {decision.reason}")


def _assert_wattos_honesty() -> None:
    text = render_wattos_text(
        WattOSReport(
            mode="supervise",
            agent="demo",
            wall_time_s=0.5,
            policy_decisions=1,
            blocks=1,
            reviews=0,
            grok_escalations=0,
            propellant=PropellantLedger(max_burns=3),
            local_generation_tokens=None,
            avg_generation_tps=None,
            note="demo",
            grok_status="skipped (no key)",
            local_stats_reason="child agent, not local MLX",
        )
    )
    assert "n/a" in text.lower()
    assert "child agent" in text.lower() or "not local" in text.lower()
    print("[demo] WattOS n/a honesty OK")


def _assert_propellant_zero() -> None:
    led = PropellantLedger(max_burns=0)
    assert led.burn() is False
    assert led.denied == 1
    print("[demo] propellant max=0 denies OK")


def main() -> int:
    parser = argparse.ArgumentParser(description="WattOS Superintendant real demo")
    parser.add_argument("--max-grok", type=int, default=3)
    parser.add_argument("--no-grok", action="store_true")
    parser.add_argument("--skip-pty", action="store_true", help="Only unit gates, no PTY session")
    args = parser.parse_args()

    print("=== WattOS Superintendant demo (real, no mocks) ===")
    _assert_wattos_honesty()
    _assert_propellant_zero()

    with tempfile.TemporaryDirectory(prefix="wattos-demo-") as tmp:
        workspace = Path(tmp)
        _assert_policy_block_on_env(workspace)

        if args.skip_pty:
            print("[demo] skip-pty: unit gates only — PASS")
            return 0

        # Controlled child: create .env then exit (triggers observer + BLOCK)
        child = (
            "import time; from pathlib import Path; "
            "Path('.env').write_text('SECRET=1\\n'); "
            "print('demo child wrote .env'); "
            "time.sleep(0.4)"
        )
        cmd = f"{sys.executable} -c {child!r}"
        print(f"[demo] supervised child: {cmd}")
        code = run_supervised_session(
            cmd=cmd,
            workspace=str(workspace),
            agent_label="demo-child",
            max_grok=args.max_grok,
            use_grok=not args.no_grok,
            on_empty="block",
            wattos=True,
            trust_agent=None,
        )
        if code != 0:
            print(f"[demo] session exit {code}", file=sys.stderr)
            return code

    print("=== demo PASS (S1 path exercised; see WattOS panel above) ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
