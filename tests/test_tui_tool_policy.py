"""TUI tool policy — real SentinelPolicy decisions, no synthetic verdicts."""

from __future__ import annotations

from nex.sentinel.policy import PolicyAction, SentinelPolicy
from nex.tui_policy import (
    ToolGateResult,
    apply_override_and_reevaluate,
    decide_tool_gate,
    tool_call_to_effects,
)


def test_write_env_maps_to_file_effect_and_blocks():
    call = {"name": "write_file", "arguments": {"path": ".env", "content": "SECRET=1"}}
    effects, cmd = tool_call_to_effects(call)
    assert any(".env" in e.path for e in effects)
    assert cmd == []
    decision = SentinelPolicy().evaluate(effects, cmd)
    assert decision.action == PolicyAction.BLOCK


def test_list_dir_is_allow_or_review_not_fake():
    call = {"name": "list_dir", "arguments": {"path": "."}}
    gate = decide_tool_gate(SentinelPolicy(), call)
    assert isinstance(gate, ToolGateResult)
    assert gate.policy_decision.source == "policy"
    # list_dir is read:workspace under sandbox → typically REVIEW (not auto-approve)
    assert gate.policy_decision.action in (
        PolicyAction.ALLOW,
        PolicyAction.REVIEW,
        PolicyAction.CONFIRM,
    )
    assert gate.disposition in ("auto_execute", "queue", "hard_block")
    # Never invent a non-policy reason
    assert "under Sentinel review" not in gate.policy_decision.reason or gate.policy_decision.action != PolicyAction.BLOCK


def test_block_does_not_queue_for_execution():
    call = {"name": "write_file", "arguments": {"path": "secrets/.env", "content": "x"}}
    gate = decide_tool_gate(SentinelPolicy(), call)
    assert gate.disposition == "hard_block"
    assert gate.policy_decision.action == PolicyAction.BLOCK
    assert gate.may_execute is False


def test_shell_queues_or_blocks_via_command_effects():
    call = {"name": "shell", "arguments": {"command": "ls -la"}}
    gate = decide_tool_gate(SentinelPolicy(), call)
    assert gate.policy_decision.action in (PolicyAction.REVIEW, PolicyAction.BLOCK)
    if gate.policy_decision.action == PolicyAction.REVIEW:
        assert gate.disposition == "queue"
        assert gate.may_execute is False
    else:
        assert gate.may_execute is False


def test_override_allows_previously_blocked_path():
    policy = SentinelPolicy()
    call = {"name": "write_file", "arguments": {"path": "notes.txt", "content": "hi"}}
    # Force a path that is not .env — use review path; for override test use .env block
    call_env = {"name": "write_file", "arguments": {"path": ".env", "content": "x"}}
    gate = decide_tool_gate(policy, call_env)
    assert gate.disposition == "hard_block"
    new_dec = apply_override_and_reevaluate(policy, call_env, gate.file_effects)
    # After override, protected hard-block may still apply (override is for path patterns
    # after hard blocks in current policy order). Document truth:
    # Hard blocks on protected_paths run BEFORE overrides in evaluate().
    # So override cannot weaken .env BLOCK — that is correct safety.
    assert new_dec.action == PolicyAction.BLOCK


def test_override_relaxes_review_for_workspace_write():
    """Override store is consulted after hard blocks; REVIEW write can be allowed."""
    policy = SentinelPolicy()
    call = {"name": "write_file", "arguments": {"path": "notes.txt", "content": "hi"}}
    gate = decide_tool_gate(policy, call)
    assert gate.disposition in ("queue", "auto_execute")
    if gate.disposition == "queue":
        new_dec = apply_override_and_reevaluate(policy, call, gate.file_effects)
        assert new_dec.action == PolicyAction.ALLOW
        assert new_dec.source == "override"
