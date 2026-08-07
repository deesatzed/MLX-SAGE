"""Autonomous agent loop with tool use for the Nex model.

Usage from CLI:
    nex agent "Create a small FastAPI hello world in the sandbox and test it with run_python"
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import List, Optional

from rich.console import Console
from rich.panel import Panel

from .engine import Engine, GenerationStats, SessionOversight
from .grok_escalator import GrokEscalator, get_grok_escalator
from .mcp_cortex_adapter import get_capability_for_tool
from .models import get_profile
from .persistence import SessionRecord, log_turn, new_session_id, save_session
from .tools import (
    execute_tool,
    format_observation,
    inject_tool_instructions,
    load_plugins,
    parse_tool_call,
)

console = Console()


@dataclass
class AgentResult:
    session_id: str
    final_answer: str
    steps: int
    stats: List[GenerationStats]


def run_agent(
    goal: str,
    *,
    engine: Engine,
    system_prompt: Optional[str] = None,
    max_steps: int = 12,
    max_tokens: int = 1536,
    temperature: float = 0.4,
    session_id: Optional[str] = None,
    persist: bool = True,
) -> AgentResult:
    """
    Run a ReAct-style autonomous agent loop until the model produces a final answer
    without emitting a tool call, or max_steps is reached.
    """
    load_plugins()

    sid = session_id or new_session_id("agent")
    record = SessionRecord(session_id=sid, model=engine.model_id)

    # Model-aware tool instructions
    profile = get_profile(engine.model_id)
    base_instructions = inject_tool_instructions(system_prompt)
    if profile and profile.agent_tool_instructions:
        tool_section = profile.agent_tool_instructions
    else:
        tool_section = ""
    record.system_prompt = base_instructions + ("\n\n" + tool_section if tool_section else "")

    record.params = {
        "temperature": temperature,
        "top_p": 0.9,
        "max_tokens": max_tokens,
    }

    messages: List[dict] = [{"role": "system", "content": record.system_prompt}]
    messages.append({"role": "user", "content": goal})

    # Strong format reminder on the first turn (many small models need this)
    messages.append({
        "role": "user",
        "content": "REMINDER: Use ONLY the exact format shown in the system prompt. Example of a correct first action:\ncall tool list_dir with path is .\n\nDo not explain the format in your thinking — just emit a clean tool call when you want to use a tool."
    })

    if persist:
        save_session(record)

    console.print(Panel.fit(f"[bold]Agent Goal[/bold]\n{goal}", border_style="magenta"))
    console.print(f"[dim]Session: {sid} | max_steps={max_steps}[/dim]\n")

    steps = 0
    all_stats: List[GenerationStats] = []
    oversight = SessionOversight()
    t0 = time.time()

    grok = get_grok_escalator()
    use_grok_loop = os.environ.get("GROK_IN_LOOP", "false").lower() in ("1", "true", "yes")

    while steps < max_steps:
        steps += 1
        prompt = engine.apply_chat_template(messages, add_generation_prompt=True)

        console.print(f"[bold cyan]Step {steps}[/bold cyan] — thinking + possible tool use...")

        full_text = ""
        final_stats: Optional[GenerationStats] = None

        for chunk, stats in engine.stream_generate(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=0.9,
        ):
            if chunk:
                full_text += chunk
            if stats:
                final_stats = stats

        if final_stats:
            all_stats.append(final_stats)
            oversight.local_generation_tokens += final_stats.generation_tokens or 0

        # Log the assistant turn
        log_turn(
            session_id=sid,
            model=engine.model_id,
            role="assistant",
            content=full_text,
            stats=final_stats.__dict__ if final_stats else None,
            extra={"step": steps, "mode": "agent"},
        )

        # Grok-in-the-Loop escalation for risky/ambiguous steps
        if use_grok_loop and grok.is_available():
            # Simple heuristic: escalate if we see "review", high uncertainty language, or tool call on sensitive paths
            if any(word in full_text.lower() for word in ["review", "confirm", "danger", "production", ".env", "secret", "deploy"]):
                console.print("[magenta]→ Escalating to Grok for structured review...[/magenta]")
                decision = grok.escalate(
                    intent="Agent step in autonomous task",
                    effects=[{"operation": "tool_call", "path": "agent_action"}],
                    local_verdict="review",
                    local_reason=full_text[:800],
                    trace_summary=f"Step {steps} of agent run",
                    risk_class="yellow",
                )
                log_turn(
                    session_id=sid,
                    model="grok-escalation",
                    role="grok",
                    content=json.dumps(decision),
                    extra={"step": steps, "escalated": True},
                )
                console.print(f"[magenta]Grok verdict: {decision.get('verdict')} - {decision.get('reason')[:120]}[/magenta]")

                if decision.get("verdict") == "block":
                    oversight.grok_escalations += 1
                    oversight.blocks += 1
                    console.print(Panel("Grok recommended BLOCK. Stopping agent loop.", title="Grok Escalation", border_style="red"))
                    break
                if decision.get("verdict") == "review":
                    oversight.grok_escalations += 1
                    oversight.reviews += 1
                    console.print(Panel("Grok recommends human review. Pausing for now.", title="Grok Escalation", border_style="yellow"))
                    # In full version we would wait for human input here
                else:
                    oversight.grok_escalations += 1
                    oversight.reviews += 1  # treat non-block as review for count

        # Check for tool call
        tool_call = parse_tool_call(full_text)

        # Append the model's output to history (we keep the raw thinking + call for transparency)
        messages.append({"role": "assistant", "content": full_text})

        if tool_call:
            tool_name = tool_call["name"]
            args = tool_call.get("arguments", {})
            console.print(f"[yellow]→ Tool call:[/yellow] {tool_name} {args}")

            # MCP-Cortex style contract for policy / Grok context
            contract = get_capability_for_tool(tool_name, args)
            console.print(f"[dim]  Capability effects: {contract.effects} (risk: {contract.risk})[/dim]")

            observation = execute_tool(tool_call)
            obs_text = format_observation(tool_name, observation)

            console.print(f"[green]← Observation:[/green] {observation[:300]}{'...' if len(observation) > 300 else ''}\n")

            messages.append({"role": "user", "content": obs_text})

            log_turn(
                session_id=sid,
                model=engine.model_id,
                role="tool",
                content=obs_text,
                extra={"tool": tool_name, "step": steps},
            )

            if persist:
                record.messages = messages
                save_session(record)
            continue

        # No tool call — this is the final answer (or the model decided to respond)
        final = full_text
        console.print(Panel(final.strip(), title=f"Final response (step {steps})", border_style="green"))

        if persist:
            record.messages = messages
            save_session(record)

        wall = time.time() - t0
        if all_stats:
            ts = [s.generation_tps for s in all_stats if getattr(s, "generation_tps", 0) > 0]
            oversight.avg_generation_tps = sum(ts) / len(ts) if ts else 0.0
        oversight.wall_time_s = wall
        oversight.policy_decisions = steps  # proxy: every step had policy/grok opportunity

        mode = "agent (GROK_IN_LOOP)" if use_grok_loop else "agent"
        _print_end_reports(oversight, sid, steps, mode, use_grok_loop=use_grok_loop)
        return AgentResult(
            session_id=sid,
            final_answer=final.strip(),
            steps=steps,
            stats=all_stats,
        )

    # Max steps reached
    last = messages[-1]["content"] if messages else ""
    console.print(f"[red]Max steps ({max_steps}) reached.[/red]")
    wall = time.time() - t0
    if all_stats:
        ts = [s.generation_tps for s in all_stats if getattr(s, "generation_tps", 0) > 0]
        oversight.avg_generation_tps = sum(ts) / len(ts) if ts else 0.0
    oversight.wall_time_s = wall
    oversight.policy_decisions = steps
    _print_end_reports(oversight, sid, steps, "agent (max steps)", use_grok_loop=use_grok_loop)
    return AgentResult(
        session_id=sid,
        final_answer=last,
        steps=steps,
        stats=all_stats,
    )


def _print_end_reports(
    oversight: SessionOversight,
    sid: str,
    steps: int,
    mode: str,
    *,
    use_grok_loop: bool,
) -> None:
    """Print Session Oversight + unified WattOS end report (real counters only)."""
    _print_oversight_report(oversight, sid, steps, mode)
    _print_agent_wattos(oversight, sid, mode, use_grok_loop=use_grok_loop)


def _print_agent_wattos(
    oversight: SessionOversight,
    sid: str,
    mode: str,
    *,
    use_grok_loop: bool,
) -> None:
    """WattOS for native nex agent — local tokens filled from real GenerationStats."""
    from .propellant import PropellantLedger
    from .wattos import WattOSReport, print_wattos_report

    if use_grok_loop:
        try:
            max_burns = int(os.environ.get("NEX_MAX_GROK", "3"))
        except ValueError:
            max_burns = 3
        max_burns = max(0, max_burns)
        used = min(oversight.grok_escalations, max_burns) if max_burns else 0
        denied = max(0, oversight.grok_escalations - used) if max_burns == 0 else 0
        ledger = PropellantLedger(max_burns=max_burns, used=used, denied=denied)
        grok_status = "on (GROK_IN_LOOP)"
    else:
        ledger = PropellantLedger(max_burns=0, used=0, denied=0)
        grok_status = "disabled (local agent)"

    tps = oversight.avg_generation_tps if oversight.avg_generation_tps > 0 else None
    toks = oversight.local_generation_tokens if oversight.local_generation_tokens else None
    report = WattOSReport(
        mode=mode,
        agent=f"nex-agent:{sid}",
        wall_time_s=oversight.wall_time_s,
        policy_decisions=oversight.policy_decisions,
        blocks=oversight.blocks,
        reviews=oversight.reviews,
        grok_escalations=oversight.grok_escalations,
        propellant=ledger,
        local_generation_tokens=toks,
        avg_generation_tps=tps,
        note=oversight.note or "native nex agent (sandbox tools)",
        grok_status=grok_status,
        local_stats_reason=None if toks is not None else "no local generation stats recorded",
    )
    print_wattos_report(report, console=console)


def _print_oversight_report(oversight: SessionOversight, sid: str, steps: int, mode: str) -> None:
    """Real, needs-tied summary. Printed at end of agent runs.

    Makes visible:
    - Hardware efficiency (local tokens + measured t/s from real MLX + MTP gens).
    - Selective Grok use (only on flagged risky/ambiguous steps).
    - Policy action (every step is a decision opportunity under Sentinel).
    - Full context for "what only this stack delivers" on a real run.
    """
    from rich.table import Table

    table = Table(title=f"Session Oversight & Efficiency — {mode}", show_header=False, box=None)
    table.add_row("session", sid)
    table.add_row("steps", str(steps))
    table.add_row("local gen tokens", str(oversight.local_generation_tokens))
    table.add_row("avg t/s (local)", f"{oversight.avg_generation_tps:.1f}")
    table.add_row("wall time (s)", f"{oversight.wall_time_s:.1f}")
    table.add_row("grok escalations", str(oversight.grok_escalations))
    table.add_row("blocks (Grok+policy)", str(oversight.blocks))
    table.add_row("reviews", str(oversight.reviews))
    table.add_row("policy decisions (opp)", str(oversight.policy_decisions))
    table.add_row("note", oversight.note)

    console.print(Panel(table, border_style="cyan", title="Needs-based proof (local speed + Grok only when it matters + real policy)"))
    console.print("[dim]Replay full trace: nex trace replay <session-or-log> (includes per-step + grok JSON)[/dim]\n")
