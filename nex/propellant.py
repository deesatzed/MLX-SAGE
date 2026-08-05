"""Propellant ledger: cap Grok escalation burns per session.

1 burn = 1 Grok escalation API attempt that was actually started.
No mocks. Local MLX does not consume propellant.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class PropellantLedger:
    max_burns: int = 3
    used: int = 0
    denied: int = 0

    def __post_init__(self) -> None:
        if self.max_burns < 0:
            raise ValueError("max_burns must be >= 0")

    @property
    def remaining(self) -> int:
        return max(0, self.max_burns - self.used)

    def can_burn(self) -> bool:
        return self.used < self.max_burns

    def burn(self) -> bool:
        """Consume one burn if available. Returns True if burned, False if denied."""
        if not self.can_burn():
            self.denied += 1
            return False
        self.used += 1
        return True

    def record_denied(self) -> None:
        """Count a would-be burn blocked without calling burn() (e.g. pre-check path)."""
        self.denied += 1

    def snapshot(self) -> Dict[str, Any]:
        return {
            "propellant_max": self.max_burns,
            "propellant_used": self.used,
            "propellant_remaining": self.remaining,
            "propellant_denied": self.denied,
        }
