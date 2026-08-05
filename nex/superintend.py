"""Shared Superintendant session: PTY + enforcer + propellant + WattOS.

Used by `nex supervise` and scripts/grok-claude / grok-codex.
No mocks. Grok burns only when remote API is available and used.
"""

from __future__ import annotations

import re
import sys
import time
from typing import Optional

from rich.console import Console

from .engine import Engine
from .propellant import PropellantLedger
from .sentinel.enforcer import ContinuousEnforcer, FileEffectObserver
from .sentinel.grok_auditor import GrokAugmentedAuditor
from .sentinel.policy import SentinelPolicy
from .sentinel.pty_runner import PtyAgentRunner
from .wattos import WattOSReport, print_wattos_report

console = Console()

VALID_ON_EMPTY = ("human_or_block", "block", "allow_local_only")


def run_supervised_session(
    *,
    cmd: str,
    workspace: str,
    agent_label: str = "agent",
    max_grok: int = 3,
    use_grok: bool = True,
    on_empty: str = "human_or_block",
    wattos: bool = True,
    trust_agent: Optional[str] = None,
) -> int:
    """Run PTY child under Sentinel + propellant-capped Grok. Returns 0 on clean end."""
    if on_empty not in VALID_ON_EMPTY:
        console.print(f"[red]Invalid on_empty={on_empty}[/red]")
        return 2

    engine = Engine()
    policy = SentinelPolicy()
    auditor = GrokAugmentedAuditor(engine, use_grok=use_grok)
    ledger = PropellantLedger(max_burns=max_grok)
    grok_available = bool(
        use_grok
        and getattr(auditor, "grok", None) is not None
        and auditor.grok.is_available()
    )
    grok_status_parts: list[str] = []
    if not use_grok:
        grok_status_parts.append("disabled (--no-grok)")
    elif not grok_available:
        grok_status_parts.append("skipped (no key)")

    console.print(f"[bold cyan]Starting Superintendant for {agent_label}[/bold cyan]: {cmd}")
    console.print(
        f"Propellant max={max_grok} · grok={'on' if use_grok else 'off'} · "
        f"api={'ready' if grok_available else 'unavailable'} · WattOS={'on' if wattos else 'off'}"
    )

    runner = PtyAgentRunner(cmd, cwd=workspace)
    runner.start()

    observer = FileEffectObserver(workspace)
    observer.snapshot()
    enforcer = ContinuousEnforcer(
        policy=policy,
        observer=observer,
        grok_escalator=auditor.grok if grok_available else None,
        on_block=lambda dec, effs: console.print(f"[ENFORCER BLOCK] {dec.reason} for {effs}"),
    )
    enforcer.start()

    grok_escalations = 0
    blocks = 0
    reviews = 0
    policy_decisions = 0
    t0 = time.time()

    def _apply_on_empty() -> str:
        if on_empty == "allow_local_only":
            return "allow"
        if on_empty == "block":
            return "block"
        if sys.stdin.isatty():
            console.print(
                "[yellow]Propellant empty or Grok unavailable — default BLOCK "
                "(no interactive REVIEW UI in v1 PTY)[/yellow]"
            )
        return "block"

    try:
        while runner.is_alive():
            output = runner.get_output(timeout=0.3)
            if not output:
                continue
            console.print(f"[{agent_label.upper()}] {output.strip()[:120]}")

            decision = enforcer.check_once() or policy.evaluate([])
            policy_decisions += 1

            if decision.action.value == "block":
                blocks += 1
                console.print(f"[POLICY BLOCK] {decision.reason}")
                runner.write_input("n\n")
                continue

            if decision.action.value in ("review", "confirm"):
                reviews += 1
                grok_verdict = None

                if not use_grok or not grok_available:
                    if _apply_on_empty() == "block":
                        blocks += 1
                        runner.write_input("n\n")
                        continue
                elif not ledger.can_burn():
                    ledger.record_denied()
                    console.print("[Propellant] denied — empty")
                    if _apply_on_empty() == "block":
                        blocks += 1
                        runner.write_input("n\n")
                        continue
                else:
                    if not ledger.burn():
                        if _apply_on_empty() == "block":
                            blocks += 1
                            runner.write_input("n\n")
                            continue
                    else:
                        grok = auditor.audit(
                            f"{agent_label} action", output, risk=decision.risk
                        )
                        if grok.get("grok_escalated"):
                            grok_escalations += 1
                        else:
                            ledger.used = max(0, ledger.used - 1)
                            grok_status_parts.append("no remote escalate (refunded)")
                        grok_verdict = grok.get("verdict")
                        console.print(
                            f"[GROK] {grok_verdict}: {grok.get('reason', '')[:80]}"
                        )
                        if grok_verdict == "block":
                            blocks += 1
                            runner.write_input("n\n")
                            continue

                console.print(
                    f"[PENDING] policy={decision.action.value} grok={grok_verdict}"
                )

            ta = trust_agent or agent_label
            if ta == "claude" and re.search(r"trust|confirm|exit", output, re.I):
                runner.write_input("n\n")
            if ta == "codex" and re.search(r"trust|proceed|run", output, re.I):
                runner.write_input("y\n")
    except KeyboardInterrupt:
        console.print("\n[Sentinel] Killed by user.")
    finally:
        enforcer.stop()
        runner.kill()
        wall = time.time() - t0
        if not grok_status_parts:
            if grok_escalations:
                grok_status_parts.append(f"ok ({grok_escalations} burns)")
            elif use_grok and grok_available:
                grok_status_parts.append("ready (no burns this session)")
            else:
                grok_status_parts.append("idle")
        if wattos:
            print_wattos_report(
                WattOSReport(
                    mode="supervise",
                    agent=agent_label,
                    wall_time_s=wall,
                    policy_decisions=policy_decisions,
                    blocks=blocks,
                    reviews=reviews,
                    grok_escalations=grok_escalations,
                    propellant=ledger,
                    local_generation_tokens=None,
                    avg_generation_tps=None,
                    note=f"workspace={workspace}; external agent under Sentinel",
                    grok_status="; ".join(dict.fromkeys(grok_status_parts)),
                    local_stats_reason="child agent, not local MLX",
                )
            )
        console.print("[Sentinel] Supervision ended.")
    return 0
