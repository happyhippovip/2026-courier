#!/usr/bin/env python3
"""Product-4C shadow batch selector. It never dispatches or mutates the live runtime."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List

from scripts.elite_execution_core import CapabilityType, EliteActionSpec, QualityFloorClass, SchedulerDecision
from scripts.organization_elite_policy import CentralElitePolicyRegistry
from scripts.productivity_engine import ProductivityEngine, WorkCandidate


COURIER_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class BatchItem:
    task_id: str
    worker: str
    provider: str
    scope: str
    reason: str
    completion_status: str = "OPEN"


def _scope_conflict(left: str, right: str) -> bool:
    left, right = left.strip().rstrip("/"), right.strip().rstrip("/")
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


class ParallelDispatchReadyPack:
    """Selection-only batch planning that reuses existing policy and FastFinish admission semantics."""

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = Path(repo_dir)
        self.engine = ProductivityEngine(self.repo_dir)
        self.registry = CentralElitePolicyRegistry(repo_dir=self.repo_dir)
        self._accepted_fingerprints: set[str] = set()

    @staticmethod
    def _floor(candidate: WorkCandidate) -> QualityFloorClass:
        if candidate.money_gate:
            return QualityFloorClass.MONEY
        if candidate.publication_gate or candidate.human_gate:
            return QualityFloorClass.PUBLICATION
        if candidate.risk.upper() in {"HIGH", "SECURITY"}:
            return QualityFloorClass.SECURITY
        return QualityFloorClass.MEDIUM_RISK if candidate.decision_value in {"HIGH_VALUE", "CRITICAL_UNBLOCK"} else QualityFloorClass.LOW_RISK

    @staticmethod
    def _provider(worker: str, workers: Dict[str, Dict[str, Any]]) -> str:
        return str(workers[worker].get("provider", worker.upper()))

    def _stable_fingerprint(self, items: List[BatchItem]) -> str:
        raw = [(item.task_id, item.worker, item.provider, item.scope) for item in sorted(items, key=lambda value: value.task_id)]
        return hashlib.sha256(json.dumps(raw, separators=(",", ":")).encode("utf-8")).hexdigest()

    def select_dispatch_batch(
        self,
        candidates: Iterable[WorkCandidate],
        workers: Dict[str, Dict[str, Any]],
        completed_task_ids: Iterable[str] = (),
        accepted_fingerprints: Iterable[str] = (),
        deterministic_resolver=None,
    ) -> Dict[str, Any]:
        """Return 0..2 shadow dispatch candidates. No envelope is created and no runtime state changes."""
        candidates = list(candidates)
        accepted = set(accepted_fingerprints) | self._accepted_fingerprints
        advisory = self.engine.plan(candidates, workers, completed_task_ids, accepted)
        by_id = {candidate.task_id: candidate for candidate in candidates}
        selected: List[BatchItem] = []
        withheld: Dict[str, str] = {task["task_id"]: task["state"] for task in advisory["tasks"] if task["state"] != "READY"}

        for recommendation in advisory["dispatch_advisory"]:
            if len(selected) >= 2:
                withheld[recommendation["task_id"]] = "WORKER_LIMIT"
                continue
            candidate = by_id[recommendation["task_id"]]
            if candidate.semantic_fingerprint and candidate.semantic_fingerprint in accepted:
                withheld[candidate.task_id] = "DUPLICATE_SEMANTIC_WORK"
                continue
            if any(_scope_conflict(candidate.scope, item.scope) for item in selected):
                withheld[candidate.task_id] = "SCOPE_CONFLICT"
                continue
            if self.registry.snitch_manager.is_scope_quarantined(candidate.scope):
                withheld[candidate.task_id] = "QUARANTINED_BY_SNITCH"
                continue

            spec = EliteActionSpec(
                action_id=candidate.task_id, goal=candidate.goal, expected_unlock=candidate.expected_useful_outcome,
                quality_floor=self._floor(candidate), risk_class=candidate.risk,
                new_information="PRODUCT_2C_SELECTED", why_now="SAFE_BATCH_CANDIDATE",
                why_model="", why_not_local="", why_not_cache="",
                decision_value_class=candidate.decision_value, mutation_scope=[candidate.scope],
                is_on_critical_path=candidate.critical_path,
            )
            plan = self.registry.fast_finish_engine.evaluate_and_schedule_plan(
                [spec], "PRODUCT_4C_SHADOW", deterministic_resolver=deterministic_resolver,
                snitch_manager=self.registry.snitch_manager,
            )
            admission = plan.get("admissions", {}).get(candidate.task_id, {})
            if not admission.get("admitted"):
                withheld[candidate.task_id] = str(admission.get("decision", "AUTHORITATIVE_DENIAL"))
                continue

            selected.append(BatchItem(
                task_id=candidate.task_id, worker=recommendation["worker"],
                provider=self._provider(recommendation["worker"], workers), scope=candidate.scope,
                reason=candidate.priority_reason,
            ))

        batch_id = self._stable_fingerprint(selected) if selected else None
        return {
            "mode": "SHADOW_READY_PACK", "batch_id": batch_id,
            "decision_fingerprint": batch_id,
            "selected_jobs": [asdict(item) for item in selected],
            "withheld": withheld,
            "safe_idle_reason": "NO_ELIGIBLE_WORK" if not selected else None,
            "model_calls_for_read": 0,
            "creates_runtime_jobs": False,
        }

    def completion_stamp(self, task_id: str, semantic_fingerprint: str, result_reference: str | None) -> Dict[str, str]:
        """Passive compatibility stamp; DONE is impossible without a result reference."""
        if result_reference:
            if semantic_fingerprint:
                self._accepted_fingerprints.add(semantic_fingerprint)
            return {"task_id": task_id, "status": "DONE", "result_reference": result_reference}
        return {"task_id": task_id, "status": "NOT_DONE", "result_reference": ""}

    def cockpit_snapshot(self, batch: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "batch_id": batch.get("batch_id"), "decision_fingerprint": batch.get("decision_fingerprint"),
            "selected_jobs": batch.get("selected_jobs", []), "withheld": batch.get("withheld", {}),
            "safe_idle_reason": batch.get("safe_idle_reason"), "model_calls_for_read": 0,
        }
