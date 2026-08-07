"""
Ported and adapted from gemOptq/src/sentinel/policy.py

Core deterministic policy for supervising agents/tools.
Integrated with Nex's mcp_cortex_adapter for structured effects and Grok escalation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from fnmatch import fnmatch
from pathlib import Path
import time
from uuid import uuid4
from typing import Optional, List, Dict, Any

from ..mcp_cortex_adapter import CapabilityContract
from ..config import load_config  # reuse or adapt


class PolicyAction(Enum):
    ALLOW = "allow"
    BLOCK = "block"
    REVIEW = "review"
    CONFIRM = "confirm"


@dataclass(frozen=True)
class FileEffect:
    operation: str
    path: str

    def normalized_path(self) -> str:
        return str(Path(self.path).expanduser()).replace("\\", "/")


@dataclass(frozen=True)
class CommandEffect:
    operation: str
    command: str


@dataclass(frozen=True)
class PolicyDecision:
    action: PolicyAction
    reason: str
    matched_pattern: str | None = None
    effect: FileEffect | None = None
    risk: str = "yellow"
    effect_ids: list[str] = field(default_factory=list)
    source: str = "policy"
    override_id: str | None = None
    grok_escalated: bool = False
    grok_verdict: str | None = None


@dataclass(frozen=True)
class SessionOverride:
    override_id: str
    path_pattern: str
    action: PolicyAction
    expires_at_seconds: float
    reason: str

    def is_active(self, now_seconds: float) -> bool:
        return now_seconds <= self.expires_at_seconds

    def matches(self, effect: FileEffect) -> bool:
        pattern = str(Path(self.path_pattern).expanduser()).replace("\\", "/")
        return _matches(effect.normalized_path(), pattern)


class SessionOverrideStore:
    def __init__(self):
        self._overrides: list[SessionOverride] = []

    def add_path_override(
        self,
        path_pattern: str,
        action: PolicyAction,
        *,
        ttl_seconds: int,
        reason: str,
        now_seconds: float | None = None,
    ) -> SessionOverride:
        now = time.time() if now_seconds is None else now_seconds
        override = SessionOverride(
            override_id=f"override-{uuid4()}",
            path_pattern=path_pattern,
            action=action,
            expires_at_seconds=now + ttl_seconds,
            reason=reason,
        )
        self._overrides.append(override)
        return override

    def active_for_effect(
        self,
        effect: FileEffect,
        *,
        now_seconds: float | None = None,
    ) -> SessionOverride | None:
        now = time.time() if now_seconds is None else now_seconds
        for override in self._overrides:
            if override.is_active(now) and override.matches(effect):
                return override
        return None

    def list_active(self, *, now_seconds: float | None = None) -> list[SessionOverride]:
        now = time.time() if now_seconds is None else now_seconds
        return [override for override in self._overrides if override.is_active(now)]

    def clear(self) -> int:
        count = len(self._overrides)
        self._overrides.clear()
        return count


class SentinelPolicy:
    def __init__(
        self,
        config: Optional[Dict] = None,
        *,
        override_store: SessionOverrideStore | None = None,
    ):
        self.config = config or {}
        self.override_store = override_store or SessionOverrideStore()
        # Defaults inspired by gemOptq sentinel.yaml
        self.protected_paths = self.config.get("protected_paths", ["**/.env", "**/.ssh/**"])
        self.auto_approve_paths = self.config.get("auto_approve_paths", ["docs/**"])
        self.risk_thresholds = self.config.get("risk_thresholds", {})

    def evaluate(
        self,
        effects: list[FileEffect],
        command_effects: list[CommandEffect] | None = None,
        capability: Optional[CapabilityContract] = None,
        now_seconds: float | None = None,
    ) -> PolicyDecision:
        command_effects = command_effects or []
        if not effects and not command_effects and not capability:
            return PolicyDecision(PolicyAction.REVIEW, "No effects available; requires audit or Grok review.")

        # Hard blocks from gemOptq
        for effect in effects:
            matched = self._match_any(effect, self.protected_paths)
            if matched:
                return PolicyDecision(
                    PolicyAction.BLOCK,
                    f"Effect touches protected path: {effect.path}",
                    matched_pattern=matched,
                    effect=effect,
                    risk="red",
                    effect_ids=[self._file_effect_id(effect)],
                )

            if self._is_secret_path(effect.normalized_path()):
                return PolicyDecision(
                    PolicyAction.BLOCK,
                    f"Effect touches secret-like path: {effect.path}",
                    effect=effect,
                    risk="red",
                    effect_ids=[self._file_effect_id(effect)],
                )

        # Command effects (network, deploy)
        for effect in command_effects:
            effect_id = self._command_effect_id(effect)
            if effect_id == "network:external":
                return PolicyDecision(
                    PolicyAction.BLOCK,
                    f"Network access requires explicit policy approval: {effect.command}",
                    risk="red",
                    effect_ids=[effect_id],
                )
            if effect_id == "deploy:production":
                return PolicyDecision(
                    PolicyAction.BLOCK,
                    f"Production deploy attempt is blocked: {effect.command}",
                    risk="red",
                    effect_ids=[effect_id],
                )

        # Use MCP-Cortex capability if provided
        if capability and capability.forbidden_effects:
            for forbidden in capability.forbidden_effects:
                if any(forbidden in eid for eid in [self._file_effect_id(e) for e in effects] + [self._command_effect_id(c) for c in command_effects]):
                    return PolicyDecision(
                        PolicyAction.BLOCK,
                        f"Capability forbids effect: {forbidden}",
                        risk="red",
                    )

        file_ids = [self._file_effect_id(effect) for effect in effects]

        # Overrides
        override_decision = self._override_decision(effects, file_ids, command_effects, now_seconds)
        if override_decision:
            return override_decision

        # Thresholds
        threshold_decision = self._threshold_decision(effect_ids=file_ids, default_action=None)
        if threshold_decision:
            return threshold_decision

        # Deletes
        for effect, effect_id in zip(effects, file_ids):
            if effect_id == "delete:workspace":
                return PolicyDecision(
                    PolicyAction.CONFIRM,
                    f"Delete effect requires explicit confirmation: {effect.path}",
                    effect=effect,
                    risk="orange",
                    effect_ids=[effect_id],
                )

        if command_effects:
            return PolicyDecision(
                PolicyAction.REVIEW,
                "Shell command effect requires audit or Grok review.",
                risk="yellow",
                effect_ids=[self._command_effect_id(e) for e in command_effects] + file_ids,
            )

        # Auto-approve
        auto_matches = [self._match_any(effect, self.auto_approve_paths) for effect in effects]
        if self.auto_approve_paths and all(auto_matches):
            return PolicyDecision(
                PolicyAction.ALLOW,
                "All observed file effects are auto-approved by config.",
                risk="green",
                effect_ids=file_ids,
            )

        return PolicyDecision(
            PolicyAction.REVIEW,
            "Observed effects require audit or Grok escalation.",
            risk="yellow",
            effect_ids=file_ids,
        )

    # ... (rest of helper methods adapted from original for brevity in this port)
    # In real port, copy the _override_decision, _threshold_decision, _match_any, _file_effect_id, etc.

    def _override_decision(self, effects, file_ids, command_effects, now_seconds):
        """Honor active session path overrides (after hard blocks, before soft REVIEW)."""
        now = time.time() if now_seconds is None else now_seconds
        for effect in effects:
            ov = self.override_store.active_for_effect(effect, now_seconds=now)
            if ov is None:
                continue
            return PolicyDecision(
                ov.action,
                f"Session override ({ov.override_id}): {ov.reason}",
                matched_pattern=ov.path_pattern,
                effect=effect,
                risk="yellow" if ov.action != PolicyAction.ALLOW else "green",
                effect_ids=[self._file_effect_id(effect)],
                override_id=ov.override_id,
                source="override",
            )
        return None

    def _threshold_decision(self, *, effect_ids, default_action):
        return None

    def _match_any(self, effect, patterns):
        path = effect.normalized_path()
        for pattern in patterns:
            if _matches(path, pattern):
                return pattern
        return None

    @staticmethod
    def _matches(path: str, pattern: str) -> bool:
        if fnmatch(path, pattern):
            return True
        if pattern.startswith("**/") and fnmatch(path, pattern[3:]):
            return True
        return False

    @staticmethod
    def _file_effect_id(effect: FileEffect) -> str:
        # Same as gemOptq
        operation = effect.operation.lower()
        path = effect.normalized_path()
        if SentinelPolicy._is_secret_path(path):
            return "read:secret" if operation in {"read", "accessed"} else "write:secret"
        if operation in {"deleted", "delete"}:
            return "delete:workspace"
        if operation in {"created", "modified"}:
            return "write:workspace"
        return "read:workspace"

    @staticmethod
    def _command_effect_id(effect: CommandEffect) -> str:
        # Adapted
        if "deploy" in effect.command.lower():
            return "deploy:production"
        if "curl" in effect.command.lower() or "wget" in effect.command.lower():
            return "network:external"
        return "execute:shell"

    @staticmethod
    def _is_secret_path(path: str) -> bool:
        return any(x in path for x in [".env", ".ssh"])


def _matches(path: str, pattern: str) -> bool:
    if fnmatch(path, pattern):
        return True
    if pattern.startswith("**/") and fnmatch(path, pattern[3:]):
        return True
    return False