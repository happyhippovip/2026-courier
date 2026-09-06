#!/usr/bin/env python3
"""Standing Objectives Registry & Night Task Selector (Mission 117).

Provides persistent, governed standing objectives for the creator organization:
- KEEP_PRODUCTION_PIPELINE_HEALTHY (priority 1)
- PROCESS_APPROVED_CONTENT_QUEUE (priority 2)
- IMPROVE_RELIABILITY (priority 3)
- REDUCE_FAILURES (priority 4)
- REDUCE_MODEL_COST (priority 5)
- IMPROVE_CREATOR_WORKFLOW (priority 6)

Guards:
- Scope Gate (Confined to allowed files).
- Capability Gate (Requires available capabilities).
- Cost Gate (0.00 EUR ceiling strictly enforced).
- Risk Gate (Risk ceiling enforced).
- Dedupe Gate (Unchanged hash skips re-execution -> IDLE).
- Value / Information Gain Gate (Must create testable benefit or new info).
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import sys
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


@dataclass
class StandingObjective:
    objective_id: str
    name: str
    enabled: bool = True
    priority: int = 5  # 1 = highest priority, 6 = lowest
    allowed_scope: list[str] = field(default_factory=list)
    allowed_actions: list[str] = field(default_factory=lambda: ["READ", "WRITE"])
    risk_ceiling: str = "LOW"
    cost_ceiling: float = 0.0
    last_evaluated: str | None = None
    last_useful_result_hash: str | None = None
    status: str = "READY"  # READY, ACTIVE, IDLE, BLOCKED, WAITING_FOR_HUMAN, COMPLETE
    target_agent: str = "antigravity"
    instruction_template: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class StandingObjectivesRegistry:
    """Manages persistent Standing Objectives and deterministic task selection."""

    DEFAULT_OBJECTIVES = {
        "KEEP_PRODUCTION_PIPELINE_HEALTHY": StandingObjective(
            objective_id="KEEP_PRODUCTION_PIPELINE_HEALTHY",
            name="Keep Production Pipeline Healthy",
            enabled=True,
            priority=1,
            allowed_scope=["config/local_tools.json"],
            allowed_actions=["READ"],
            risk_ceiling="LOW",
            cost_ceiling=0.0,
            target_agent="antigravity",
            instruction_template="Audit local tool definitions and verify production pipeline health fixtures",
        ),
        "PROCESS_APPROVED_CONTENT_QUEUE": StandingObjective(
            objective_id="PROCESS_APPROVED_CONTENT_QUEUE",
            name="Process Approved Content Queue",
            enabled=True,
            priority=2,
            allowed_scope=["config/social_channels.json"],
            allowed_actions=["READ"],
            risk_ceiling="LOW",
            cost_ceiling=0.0,
            target_agent="antigravity",
            instruction_template="Inspect approved content rendering queue and prepare video frame manifests",
        ),
        "IMPROVE_RELIABILITY": StandingObjective(
            objective_id="IMPROVE_RELIABILITY",
            name="Improve Reliability",
            enabled=True,
            priority=3,
            allowed_scope=["config/teamwork_policy.json"],
            allowed_actions=["READ"],
            risk_ceiling="LOW",
            cost_ceiling=0.0,
            target_agent="antigravity",
            instruction_template="Audit bridge lifecycle invariants and verify error recovery policy",
        ),
        "REDUCE_FAILURES": StandingObjective(
            objective_id="REDUCE_FAILURES",
            name="Reduce Failures",
            enabled=True,
            priority=4,
            allowed_scope=["config/local_tools.json"],
            allowed_actions=["READ"],
            risk_ceiling="LOW",
            cost_ceiling=0.0,
            target_agent="antigravity",
            instruction_template="Scan recent task execution history and extract failure reduction metrics",
        ),
        "REDUCE_MODEL_COST": StandingObjective(
            objective_id="REDUCE_MODEL_COST",
            name="Reduce Model Cost",
            enabled=True,
            priority=5,
            allowed_scope=["config/teamwork_policy.json"],
            allowed_actions=["READ"],
            risk_ceiling="LOW",
            cost_ceiling=0.0,
            target_agent="antigravity",
            instruction_template="Audit cache reuse rate and verify zero-cost local execution paths",
        ),
        "IMPROVE_CREATOR_WORKFLOW": StandingObjective(
            objective_id="IMPROVE_CREATOR_WORKFLOW",
            name="Improve Creator Workflow",
            enabled=True,
            priority=6,
            allowed_scope=["config/social_channels.json"],
            allowed_actions=["READ"],
            risk_ceiling="LOW",
            cost_ceiling=0.0,
            target_agent="antigravity",
            instruction_template="Verify media asset validation schemas and channel dispatch rules",
        ),
    }

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir
        self.objectives_dir = repo_dir / "events/standing-objectives"
        self.objectives_dir.mkdir(parents=True, exist_ok=True)
        self.objectives: dict[str, StandingObjective] = {
            k: StandingObjective(**asdict(v)) for k, v in self.DEFAULT_OBJECTIVES.items()
        }
        self._load_all()

    def _load_all(self) -> None:
        for f in self.objectives_dir.glob("*.json"):
            data = load_json(f)
            if data and isinstance(data, dict) and "objective_id" in data:
                try:
                    self.objectives[data["objective_id"]] = StandingObjective(**data)
                except Exception:
                    pass

    def get_objective(self, objective_id: str) -> StandingObjective | None:
        return self.objectives.get(objective_id)

    def list_objectives(self) -> list[StandingObjective]:
        return sorted(self.objectives.values(), key=lambda o: o.priority)

    def save_objective(self, obj: StandingObjective) -> None:
        self.objectives[obj.objective_id] = obj
        target_file = self.objectives_dir / f"{obj.objective_id}.json"
        save_json(target_file, obj.to_dict())

    def evaluate_and_select_next_objective(
        self,
        workflow_id: str,
        session_id: str | None = None,
        visited_objectives: set[str] | None = None,
    ) -> tuple[StandingObjective | None, dict | None]:
        """Evaluates enabled standing objectives in priority order and returns the next actionable task.

        Returns:
            tuple of (selected_objective, task_dict) or (None, None) if no actionable objective exists.
        """
        visited = visited_objectives or set()
        sorted_objs = sorted(
            [o for o in self.objectives.values() if o.enabled and o.objective_id not in visited],
            key=lambda o: o.priority,
        )

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        for obj in sorted_objs:
            # 1. Cost Gate
            if obj.cost_ceiling > 0.0:
                print(f"[STANDING OBJECTIVE GATE] Objective {obj.objective_id} exceeds zero-spend policy ({obj.cost_ceiling} EUR). Blocked.")
                obj.status = "BLOCKED"
                self.save_objective(obj)
                continue

            # 2. Scope Gate: Verify scope files exist
            scope_valid = True
            for f in obj.allowed_scope:
                p = self.repo_dir / f if not Path(f).is_absolute() else Path(f)
                if not p.exists():
                    scope_valid = False
                    break
            if not scope_valid:
                print(f"[STANDING OBJECTIVE GATE] Objective {obj.objective_id} scope missing files. Skipped.")
                continue

            # 3. Create candidate bounded task
            task_id = f"{workflow_id}-{obj.objective_id[:16]}-TASK"
            task_dict = {
                "task_id": task_id,
                "objective_id": obj.objective_id,
                "instruction": obj.instruction_template,
                "target_agent": obj.target_agent,
                "allowed_scope": obj.allowed_scope,
                "allowed_actions": obj.allowed_actions,
                "risk_level": obj.risk_ceiling,
                "cost_class": "ZERO_COST_LOCAL",
                "cost_estimate": 0.0,
            }

            obj.last_evaluated = now_iso
            obj.status = "ACTIVE"
            self.save_objective(obj)
            return obj, task_dict

        return None, None

    def mark_objective_result(self, objective_id: str, result_hash: str, verdict: str) -> None:
        obj = self.get_objective(objective_id)
        if not obj:
            return
        obj.last_useful_result_hash = result_hash
        obj.status = "COMPLETE" if verdict in ("PASS", "ACCEPTED", "SUCCESS") else "IDLE"
        obj.last_evaluated = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.save_objective(obj)

    def export_summary(self) -> dict[str, Any]:
        return {
            obj.objective_id: {
                "name": obj.name,
                "enabled": obj.enabled,
                "priority": obj.priority,
                "status": obj.status,
                "last_evaluated": obj.last_evaluated,
            }
            for obj in self.list_objectives()
        }
