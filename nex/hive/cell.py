"""Hive Cell v0 — real co-goal partnership session on the filesystem.

Enacts mission: co-goal, complementary roles, joint beneficence gate, receipt.
No mock partners; AI role is declared honestly (assist / local model / external).
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..mission import (
    MISSION_ONE_LINER,
    JointBeneficenceResult,
    evaluate_joint_beneficence,
)

# Default under package sessions/hive/
DEFAULT_HIVE_ROOT = Path(__file__).resolve().parents[2] / "sessions" / "hive"


@dataclass
class HiveRole:
    party: str  # "human" | "ai" | "shared"
    name: str
    responsibility: str
    needed_for: str  # what breaks if this role is absent

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HiveCell:
    cell_id: str
    co_goal: str
    orientation: str  # beyond-ego shared purpose note
    roles: List[HiveRole] = field(default_factory=list)
    beneficence: Optional[Dict[str, Any]] = None
    events: List[Dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    mission: str = MISSION_ONE_LINER

    def add_role(self, role: HiveRole) -> None:
        self.roles.append(role)
        self._event("role_added", role.to_dict())

    def set_beneficence(
        self,
        *,
        human: str,
        ai_partner: str,
        shared_or_third: str,
        mode: str = "default",
        notes: Optional[str] = None,
    ) -> JointBeneficenceResult:
        result = evaluate_joint_beneficence(
            human=human,
            ai_partner=ai_partner,
            shared_or_third=shared_or_third,
            mode=mode,
            notes=notes,
        )
        self.beneficence = result.to_dict()
        self._event("beneficence", result.to_dict())
        return result

    def log_contribution(self, party: str, action: str, detail: str = "") -> None:
        self._event(
            "contribution",
            {"party": party, "action": action, "detail": detail},
        )

    def _event(self, kind: str, payload: Dict[str, Any]) -> None:
        self.events.append(
            {"ts": time.time(), "kind": kind, "payload": payload}
        )

    def receipt(self) -> Dict[str, Any]:
        return {
            "cell_id": self.cell_id,
            "co_goal": self.co_goal,
            "orientation": self.orientation,
            "mission": self.mission,
            "roles": [r.to_dict() for r in self.roles],
            "beneficence": self.beneficence,
            "events": self.events,
            "created_at": self.created_at,
            "closed_at": time.time(),
        }

    def save(self, root: Optional[Path] = None) -> Path:
        root = Path(root or DEFAULT_HIVE_ROOT)
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{self.cell_id}.json"
        path.write_text(json.dumps(self.receipt(), indent=2), encoding="utf-8")
        return path


def create_cell(
    co_goal: str,
    *,
    orientation: str = "beyond isolated ego — contribution to shared good",
    human_name: str = "human",
    human_responsibility: str = "judgment, values, accountable decision, real-world care",
    human_needed_for: str = "meaning, ethics, and ownership of consequential acts",
    ai_name: str = "ai_partner",
    ai_responsibility: str = "draft, search, structure, tireless assist within declared limits",
    ai_needed_for: str = "speed and coverage without replacing human ownership",
) -> HiveCell:
    cell = HiveCell(
        cell_id=f"hive-{uuid.uuid4().hex[:12]}",
        co_goal=co_goal.strip(),
        orientation=orientation.strip(),
    )
    cell.add_role(
        HiveRole(
            party="human",
            name=human_name,
            responsibility=human_responsibility,
            needed_for=human_needed_for,
        )
    )
    cell.add_role(
        HiveRole(
            party="ai",
            name=ai_name,
            responsibility=ai_responsibility,
            needed_for=ai_needed_for,
        )
    )
    cell.add_role(
        HiveRole(
            party="shared",
            name="shared_good",
            responsibility="the co-goal beneficiaries / mission outcome",
            needed_for="joint beneficence — why the hive exists",
        )
    )
    cell._event("cell_created", {"co_goal": cell.co_goal})
    return cell


def load_cell(cell_id: str, root: Optional[Path] = None) -> HiveCell:
    root = Path(root or DEFAULT_HIVE_ROOT)
    path = root / f"{cell_id}.json"
    if not path.exists():
        # allow bare id or full filename
        alt = root / cell_id
        path = alt if alt.exists() else path
    data = json.loads(path.read_text(encoding="utf-8"))
    roles = [HiveRole(**r) for r in data.get("roles", [])]
    cell = HiveCell(
        cell_id=data["cell_id"],
        co_goal=data["co_goal"],
        orientation=data.get("orientation", ""),
        roles=roles,
        beneficence=data.get("beneficence"),
        events=list(data.get("events", [])),
        created_at=float(data.get("created_at") or time.time()),
        mission=data.get("mission", MISSION_ONE_LINER),
    )
    return cell
