"""Real Sentinel policy gating for Nex TUI tool calls.

Maps tool calls → FileEffect / CommandEffect, evaluates with SentinelPolicy,
and returns a disposition: auto_execute | queue | hard_block.

No synthetic PolicyDecision. No auto-execute of blocked or review tools.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .sentinel.policy import (
    CommandEffect,
    FileEffect,
    PolicyAction,
    PolicyDecision,
    SentinelPolicy,
)
from .tools import SANDBOX


@dataclass
class ToolGateResult:
    """Outcome of policy evaluation for one tool call."""

    tool_call: Dict[str, Any]
    file_effects: List[FileEffect]
    command_effects: List[CommandEffect]
    policy_decision: PolicyDecision
    disposition: str  # auto_execute | queue | hard_block
    may_execute: bool

    @property
    def prompt_line(self) -> str:
        name = self.tool_call.get("name", "?")
        args = self.tool_call.get("arguments") or {}
        brief = str(args)[:80]
        return f"tool:{name} {brief}"


def _sandbox_rel(path: str) -> str:
    """Path as it would land under sandbox (for policy path matching)."""
    raw = (path or ".").strip() or "."
    # Policy matches on path strings; use sandbox-relative form and .env basenames
    p = raw.replace("\\", "/")
    return p


def tool_call_to_effects(
    tool_call: Dict[str, Any],
) -> Tuple[List[FileEffect], List[CommandEffect]]:
    """Map a parsed tool call to concrete effects for SentinelPolicy."""
    name = (tool_call.get("name") or "").strip()
    args = tool_call.get("arguments") or {}
    if not isinstance(args, dict):
        args = {}

    file_effects: List[FileEffect] = []
    command_effects: List[CommandEffect] = []

    if name == "list_dir":
        file_effects.append(FileEffect("read", _sandbox_rel(str(args.get("path", ".")))))
    elif name == "read_file":
        file_effects.append(FileEffect("read", _sandbox_rel(str(args.get("path", "")))))
    elif name == "write_file":
        file_effects.append(FileEffect("created", _sandbox_rel(str(args.get("path", "")))))
    elif name == "run_python":
        # Creates a temp .py under sandbox and executes — write + shell-like
        file_effects.append(FileEffect("created", f"{SANDBOX.name}/__tui_run_python__.py"))
        command_effects.append(CommandEffect("execute", "python3 (run_python tool)"))
    elif name == "shell":
        cmd = str(args.get("command") or "")
        command_effects.append(CommandEffect("execute", cmd))
        # Conservative: shell may touch paths mentioned simply
        for token in cmd.split():
            if "/" in token or token.startswith("."):
                file_effects.append(FileEffect("accessed", _sandbox_rel(token)))
    else:
        # Unknown tool — force review with empty effects handled by policy
        command_effects.append(CommandEffect("execute", f"unknown_tool:{name}"))

    return file_effects, command_effects


def decide_tool_gate(
    policy: SentinelPolicy,
    tool_call: Dict[str, Any],
    *,
    now_seconds: Optional[float] = None,
) -> ToolGateResult:
    """Evaluate tool call with real policy; decide auto / queue / hard_block."""
    file_effects, command_effects = tool_call_to_effects(tool_call)
    decision = policy.evaluate(
        file_effects,
        command_effects,
        now_seconds=now_seconds,
    )

    if decision.action == PolicyAction.BLOCK:
        disposition = "hard_block"
        may_execute = False
    elif decision.action == PolicyAction.ALLOW:
        disposition = "auto_execute"
        may_execute = True
    else:
        # REVIEW, CONFIRM — human must approve before execute
        disposition = "queue"
        may_execute = False

    return ToolGateResult(
        tool_call=tool_call,
        file_effects=file_effects,
        command_effects=command_effects,
        policy_decision=decision,
        disposition=disposition,
        may_execute=may_execute,
    )


def apply_override_and_reevaluate(
    policy: SentinelPolicy,
    tool_call: Dict[str, Any],
    file_effects: List[FileEffect],
    *,
    ttl_seconds: int = 3600,
    reason: str = "TUI user override",
    now_seconds: Optional[float] = None,
) -> PolicyDecision:
    """Record path overrides then re-run policy. Hard blocks (e.g. .env) still win."""
    for effect in file_effects:
        policy.override_store.add_path_override(
            effect.path or "*",
            PolicyAction.ALLOW,
            ttl_seconds=ttl_seconds,
            reason=reason,
            now_seconds=now_seconds,
        )
    _, command_effects = tool_call_to_effects(tool_call)
    return policy.evaluate(
        file_effects,
        command_effects,
        now_seconds=now_seconds,
    )
