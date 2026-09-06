#!/usr/bin/env python3
"""Product-2C deterministic work-queue planner; local evidence only, no dispatch."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List


COURIER_DIR = Path(__file__).resolve().parent.parent
TERMINAL_STATES = {"DONE", "NO_GAIN"}
GATE_STATES = {"HUMAN_GATE", "MONEY_GATE", "PUBLICATION_GATE"}


@dataclass(frozen=True)
class WorkCandidate:
    task_id: str
    goal: str
    expected_useful_outcome: str
    owner_capability: str
    scope: str
    dependencies: tuple[str, ...] = ()
    risk: str = "LOW"
    human_gate: bool = False
    money_gate: bool = False
    publication_gate: bool = False
    provider_eligibility: tuple[str, ...] = ()
    critical_path: bool = False
    decision_value: str = "USEFUL"
    parallel_safe: bool = True
    priority_reason: str = ""
    semantic_fingerprint: str = ""
    completed: bool = False
    new_evidence: bool = True
    product_value: bool = True
    infrastructure_only: bool = False


@dataclass
class ProductivityMetrics:
    useful_tasks_completed: int = 0
    valuable_state_transitions: int = 0
    workers_productively_active: int = 0
    workers_safely_idle: int = 0
    duplicate_tasks_avoided: int = 0
    model_calls_avoided_when_provable: int = 0
    human_interventions_required: int = 0
    blocked_branches: int = 0
    parallel_independent_jobs: int = 0


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default


class ProductivityEngine:
    """Ranks safe useful work and returns an advisory plan; it never performs a dispatch."""

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = Path(repo_dir)
        self.metrics = ProductivityMetrics()

    def chief_open_loop_evidence(self) -> List[Dict[str, Any]]:
        data = _read_json(self.repo_dir / "events" / "chief-brain" / "open_loops.json", [])
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            values = data.get("open_loops", data.get("items", []))
            return [item for item in values if isinstance(item, dict)] if isinstance(values, list) else []
        return []

    def derive_candidates(self) -> List[WorkCandidate]:
        """Conservatively derive candidates only where an open loop has an id and useful outcome."""
        output = []
        for item in self.chief_open_loop_evidence():
            task_id = item.get("task_id") or item.get("loop_id") or item.get("id")
            goal = item.get("goal") or item.get("title") or item.get("description")
            outcome = item.get("expected_output") or item.get("expected_unlock") or item.get("expected_value")
            if not all(isinstance(value, str) and value.strip() for value in (task_id, goal, outcome)):
                continue
            output.append(WorkCandidate(
                task_id=task_id, goal=goal, expected_useful_outcome=outcome,
                owner_capability=str(item.get("owner_capability") or item.get("target_agent") or "LOCAL"),
                scope=str(item.get("scope") or item.get("project") or "UNKNOWN_SCOPE"),
                dependencies=tuple(item.get("dependencies", []) if isinstance(item.get("dependencies", []), list) else []),
                risk=str(item.get("risk") or "LOW"), human_gate=bool(item.get("human_gate")),
                money_gate=bool(item.get("money_gate")), publication_gate=bool(item.get("publication_gate")),
                provider_eligibility=tuple(item.get("provider_eligibility", []) if isinstance(item.get("provider_eligibility", []), list) else []),
                critical_path=bool(item.get("critical_path")), decision_value=str(item.get("decision_value") or "USEFUL"),
                parallel_safe=bool(item.get("parallel_safe", True)), priority_reason="CHIEF_OPEN_LOOP",
                semantic_fingerprint=str(item.get("semantic_fingerprint") or ""),
                new_evidence=bool(item.get("new_evidence", True)), product_value=not bool(item.get("infrastructure_only", False)),
                infrastructure_only=bool(item.get("infrastructure_only", False)),
            ))
        return output

    @staticmethod
    def _score(candidate: WorkCandidate) -> tuple[int, int, int, str]:
        value = {"CRITICAL_UNBLOCK": 4, "HIGH_VALUE": 3, "USEFUL": 2, "OPTIONAL": 1, "ZERO_GAIN": 0}.get(candidate.decision_value, 1)
        return (1 if candidate.critical_path else 0, value, 1 if candidate.product_value and not candidate.infrastructure_only else 0, candidate.task_id)

    def plan(
        self,
        candidates: Iterable[WorkCandidate],
        workers: Dict[str, Dict[str, Any]],
        completed_task_ids: Iterable[str] = (),
        accepted_fingerprints: Iterable[str] = (),
    ) -> Dict[str, Any]:
        """Return a deterministic, provider-neutral advisory queue with no model or external calls."""
        completed, accepted = set(completed_task_ids), {value for value in accepted_fingerprints if value}
        candidates = list(candidates)
        states: Dict[str, str] = {}
        eligible: List[WorkCandidate] = []
        for item in candidates:
            if item.completed or item.task_id in completed:
                states[item.task_id] = "DONE"
                self.metrics.useful_tasks_completed += 1
            elif item.decision_value == "ZERO_GAIN" or not item.expected_useful_outcome or not item.new_evidence:
                states[item.task_id] = "NO_GAIN"
                self.metrics.duplicate_tasks_avoided += 1
            elif item.semantic_fingerprint and item.semantic_fingerprint in accepted:
                states[item.task_id] = "DONE"
                self.metrics.model_calls_avoided_when_provable += 1
            elif item.human_gate:
                states[item.task_id] = "HUMAN_GATE"; self.metrics.human_interventions_required += 1
            elif item.money_gate:
                states[item.task_id] = "MONEY_GATE"; self.metrics.human_interventions_required += 1
            elif item.publication_gate:
                states[item.task_id] = "PUBLICATION_GATE"; self.metrics.human_interventions_required += 1
            elif item.dependencies and not set(item.dependencies).issubset(completed):
                states[item.task_id] = "WAITING_DEPENDENCY"
            else:
                eligible.append(item)

        selected: List[Dict[str, str]] = []
        occupied_scopes = set()
        free_workers = {name: info for name, info in workers.items() if info.get("state") == "FREE"}
        for item in sorted(eligible, key=self._score, reverse=True):
            if not item.parallel_safe or item.scope in occupied_scopes:
                states[item.task_id] = "WAITING_DEPENDENCY"
                continue
            compatible = [
                name for name, info in free_workers.items()
                if item.owner_capability in set(info.get("capabilities", []))
                and (not item.provider_eligibility or str(info.get("provider", name.upper())) in item.provider_eligibility)
            ]
            if not compatible:
                states[item.task_id] = "WAITING_DEPENDENCY"
                continue
            worker = sorted(compatible)[0]
            selected.append({"task_id": item.task_id, "worker": worker, "scope": item.scope})
            states[item.task_id] = "READY"
            occupied_scopes.add(item.scope)
            del free_workers[worker]

        self.metrics.workers_productively_active = len(selected)
        self.metrics.workers_safely_idle = len(free_workers)
        self.metrics.parallel_independent_jobs = max(0, len(selected) - 1)
        self.metrics.blocked_branches = sum(1 for state in states.values() if state in GATE_STATES or state == "BLOCKED")
        return {
            "status": "STOP_SUCCESS" if candidates and all(state in TERMINAL_STATES for state in states.values()) else ("IDLE" if not selected else "READY"),
            "tasks": [{"task_id": item.task_id, "state": states.get(item.task_id, "UNKNOWN"), "priority_reason": item.priority_reason} for item in candidates],
            "dispatch_advisory": selected,
            "capacity_purchase_candidate": None,
            "metrics": asdict(self.metrics),
            "model_calls": 0,
            "autonomous_spend_eur": 0.0,
        }
