#!/usr/bin/env python3
"""Product-3C adapter: Product-2C advice into the existing Runtime, never direct execution."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List

from scripts.live_operations_truth_contract import LiveOperationsTruthContract
from scripts.opportunity_queue import Opportunity
from scripts.productivity_engine import ProductivityEngine, WorkCandidate
from scripts.real_autonomy_runtime import RealAutonomyRuntime, SessionStatus


COURIER_DIR = Path(__file__).resolve().parent.parent


class ProductivityRuntimeBridge:
    """A narrow adapter. Product-2C selects; RealAutonomyRuntime remains the authority."""

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = Path(repo_dir)
        self.engine = ProductivityEngine(self.repo_dir)
        self.runtime = RealAutonomyRuntime(self.repo_dir)
        self.last_plan: Dict[str, Any] = {"status": "IDLE", "tasks": [], "dispatch_advisory": []}
        self.manual_intermediate_prompts = 0

    @staticmethod
    def _target_agent(candidate: WorkCandidate) -> str:
        value = candidate.owner_capability.upper()
        if value == "GOOGLE":
            return "antigravity"
        if value == "CODEX":
            return "codex"
        return "local"

    @staticmethod
    def _priority(candidate: WorkCandidate) -> int:
        return {"CRITICAL_UNBLOCK": 10, "HIGH_VALUE": 8, "USEFUL": 6, "OPTIONAL": 3}.get(candidate.decision_value, 1)

    def _completed_task_ids(self) -> set[str]:
        session = self.runtime._load_session()
        completed = set(session.jobs_completed) if session else set()
        ledger = self.runtime._load_ledger()
        for event in ledger.get("events", []):
            if event.get("event_type") == "RESULT" and isinstance(event.get("task_id"), str):
                completed.add(event["task_id"])
        return completed

    def synchronize(
        self,
        candidates: Iterable[WorkCandidate],
        workers: Dict[str, Dict[str, Any]],
        accepted_fingerprints: Iterable[str] = (),
    ) -> Dict[str, Any]:
        """Materialize only Product-2C READY advice; gates and authority are preserved downstream."""
        candidates = list(candidates)
        self.last_plan = self.engine.plan(candidates, workers, self._completed_task_ids(), accepted_fingerprints)
        states = {item["task_id"]: item["state"] for item in self.last_plan["tasks"]}
        by_id = {item.task_id: item for item in candidates}

        for advisory in self.last_plan["dispatch_advisory"]:
            candidate = by_id[advisory["task_id"]]
            if states.get(candidate.task_id) != "READY":
                continue
            # The Product-2C contract carries scope evidence.  Withhold a
            # quarantined scope before it ever reaches the shared runtime's
            # default branch fallback; an unrelated selected scope remains eligible.
            if self.runtime.snitch_manager.is_scope_quarantined(candidate.scope):
                states[candidate.task_id] = "BLOCKED"
                for item in self.last_plan["tasks"]:
                    if item["task_id"] == candidate.task_id:
                        item["state"] = "BLOCKED"
                        item["priority_reason"] = "QUARANTINED_BY_SNITCH"
                continue
            native = Opportunity(
                opportunity_id=candidate.task_id,
                source="PRODUCT_2C_BRIDGE",
                objective_id=candidate.goal,
                project=candidate.scope,
                description=candidate.goal,
                priority=self._priority(candidate),
                expected_value=candidate.expected_useful_outcome,
                expected_output=candidate.expected_useful_outcome,
                problem_or_goal=candidate.goal,
                risk=candidate.risk,
                cost_class="ZERO_COST_LOCAL",
                estimated_cost=0.0,
                target_agent=self._target_agent(candidate),
                allowed_scope=[],
                evidence={"priority_reason": candidate.priority_reason, "critical_path": candidate.critical_path},
            )
            self.runtime.opp_queue.add_opportunity(native)
        return self.last_plan

    def ensure_session(self, goal: str) -> None:
        session = self.runtime._load_session()
        if not session or session.status not in (SessionStatus.RUNNING, SessionStatus.WAITING, SessionStatus.IDLE_EXPECTED):
            self.runtime.start_night_session("product-3c-bridge", goal, max_iterations=20)

    def dispatch_one(self, goal: str, resolver: Callable[[str], tuple[bool, Any]], executor: Callable[[Any], Dict[str, Any]] | None = None) -> Dict[str, Any]:
        """Call only the existing authoritative Runtime path; no bridge-side authorization exists."""
        self.ensure_session(goal)
        return self.runtime.execute_session_step(deterministic_resolver=resolver, job_executor=executor)

    def run_until_quiescent(
        self,
        goal: str,
        candidates: Iterable[WorkCandidate],
        workers: Dict[str, Dict[str, Any]],
        resolver: Callable[[str], tuple[bool, Any]],
        max_steps: int = 10,
    ) -> List[Dict[str, Any]]:
        """Bounded safe continuation: evidence/result -> recompute -> existing runtime step."""
        transitions = []
        candidates = list(candidates)
        for _ in range(max_steps):
            plan = self.synchronize(candidates, workers)
            if not plan["dispatch_advisory"]:
                break
            result = self.dispatch_one(goal, resolver)
            transitions.append(result)
            if result.get("status") not in {"PROGRESS_MADE", "IDLE_EXPECTED"}:
                break
        return transitions

    def join_snapshot(self) -> Dict[str, Any]:
        """Stable model-free operations read contract for Product-3 UI consumers."""
        live = LiveOperationsTruthContract(self.repo_dir).snapshot()
        return {
            "queue_candidates": self.last_plan.get("tasks", []),
            "selected_tasks": self.last_plan.get("dispatch_advisory", []),
            "dispatch_decisions": self.last_plan.get("tasks", []),
            "worker_ownership": [{"task_id": item.get("task_id"), "owner": item.get("worker")} for item in self.last_plan.get("dispatch_advisory", [])],
            "blocked_reason": [item for item in self.last_plan.get("tasks", []) if item.get("state") in {"HUMAN_GATE", "MONEY_GATE", "PUBLICATION_GATE", "WAITING_DEPENDENCY"}],
            "dependency_state": [item for item in self.last_plan.get("tasks", []) if item.get("state") == "WAITING_DEPENDENCY"],
            "last_result": next((task for task in live["tasks"] if task.get("status") == "RESULT_READY"), None),
            "next_action": self.last_plan.get("dispatch_advisory", [None])[0],
            "parallel_jobs": self.last_plan.get("dispatch_advisory", []),
            "safe_idle_reason": "NO_ELIGIBLE_WORK" if not self.last_plan.get("dispatch_advisory") else None,
            "model_calls_for_read": 0,
        }
