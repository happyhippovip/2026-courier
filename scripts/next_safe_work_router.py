#!/usr/bin/env python3
"""Deterministic Next-Safe-Work Router.

Evaluates available workers against active OpportunityQueue candidates to produce
deterministic, scope-disjoint next-safe-work recommendations without human dispatch:
- 100% deterministic (0 model calls, 0 EUR spend)
- Respects historical completion fingerprints, scope exclusivity, and heavy-job limits
- Emits deduplicated next_safe_work.json and NEXT_SAFE_WORK_AVAILABLE alerts
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from live_worker_registry import (
        AvailabilityClass,
        EventType,
        LiveWorkerRegistry,
        WorkerRecord,
        WorkerState,
    )
    from opportunity_queue import Opportunity, OpportunityQueue
    from queue_hygiene_manager import QueueHygieneManager
except ImportError:
    from scripts.live_worker_registry import (
        AvailabilityClass,
        EventType,
        LiveWorkerRegistry,
        WorkerRecord,
        WorkerState,
    )
    from scripts.opportunity_queue import Opportunity, OpportunityQueue
    from scripts.queue_hygiene_manager import QueueHygieneManager


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def safe_load_json(path: Path) -> dict[str, Any]:
    try:
        if not path.is_file():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def safe_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}.{uuid.uuid4().hex[:6]}")
    temp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


@dataclass
class WorkerRecommendation:
    worker_id: str
    available: bool
    safe_task_available: bool
    task_id: Optional[str] = None
    task_fingerprint: Optional[str] = None
    scope: List[str] = field(default_factory=list)
    risk: str = "LOW"
    heavy_job: bool = False
    block_reason: Optional[str] = None
    recommended_action: str = "STANDBY_SAFE_IDLE"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class NextSafeWorkRouter:
    """Deterministic routing engine matching available workers to safe tasks."""

    HEAVY_JOB_LIMIT = 1

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir.resolve()
        self.state_dir = self.repo_dir / "events" / "runtime-state"
        self.alerts_dir = self.repo_dir / "events" / "runtime-alerts"
        self.events_dir = self.repo_dir / "events" / "worker-events"

        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.alerts_dir.mkdir(parents=True, exist_ok=True)
        self.events_dir.mkdir(parents=True, exist_ok=True)

        self.output_file = self.state_dir / "next_safe_work.json"
        self.registry = LiveWorkerRegistry(repo_dir=self.repo_dir)
        self.queue_manager = QueueHygieneManager(repo_dir=self.repo_dir)

        self._last_recommendation_hash: str = ""
        self.telemetry = {
            "routing_evaluations": 0,
            "tasks_recommended": 0,
            "duplicates_suppressed": 0,
            "model_calls": 0,
        }

    def evaluate_next_safe_work(self) -> Dict[str, Any]:
        """Evaluates all workers against active OpportunityQueue candidates."""
        self.telemetry["routing_evaluations"] += 1
        workers = self.registry.list_workers()

        # Load active opportunities
        q = OpportunityQueue(repo_dir=self.repo_dir)
        all_opps = q.list_opportunities()
        ready_tasks = [o for o in all_opps if o.status == "READY"]

        # Sort ready tasks by priority descending
        ready_tasks = sorted(ready_tasks, key=lambda x: x.priority, reverse=True)

        # Track fleet-wide claimed scopes and heavy jobs in progress
        occupied_scopes: Set[str] = set()
        active_heavy_jobs_count = 0

        for w in workers.values():
            if w.state == WorkerState.PROGRESSING.value and not w.is_expired():
                for s in w.mutable_scope:
                    occupied_scopes.add(s)
                if w.heavy_job:
                    active_heavy_jobs_count += 1

        recommendations: Dict[str, Dict[str, Any]] = {}
        assigned_tasks_this_cycle: Set[str] = set()
        assigned_scopes_this_cycle: Set[str] = set()

        for wid in sorted(workers.keys()):
            worker = workers[wid]

            # Check worker availability & temporary expiry
            if worker.is_expired():
                recommendations[wid] = WorkerRecommendation(
                    worker_id=wid,
                    available=False,
                    safe_task_available=False,
                    block_reason="30_DAY_RESOURCE_WINDOW_EXPIRED",
                    recommended_action="RENEW_SESSION_REQUIRED",
                ).to_dict()
                continue

            is_available = worker.state in (WorkerState.AVAILABLE.value, WorkerState.SAFE_IDLE.value)
            if not is_available:
                recommendations[wid] = WorkerRecommendation(
                    worker_id=wid,
                    available=False,
                    safe_task_available=False,
                    task_id=worker.task_id,
                    scope=worker.mutable_scope,
                    heavy_job=worker.heavy_job,
                    block_reason=f"WORKER_STATE_{worker.state}",
                    recommended_action=f"MONITOR_ACTIVE_{worker.state}",
                ).to_dict()
                continue

            # Candidate search for available worker
            candidate_found = False
            for candidate in ready_tasks:
                if candidate.opportunity_id in assigned_tasks_this_cycle:
                    continue

                # 1. Historical completed fingerprint check
                if self.queue_manager.is_task_completed_in_history(candidate.opportunity_id):
                    continue

                # 2. Spend firewall check (Strict 0.00 EUR)
                if candidate.estimated_cost > 0.0 or candidate.status == "PAYMENT_APPROVAL_REQUIRED":
                    continue

                # 3. High risk & Human approval check
                if candidate.risk == "HIGH" or candidate.status in ("WAITING_FOR_HUMAN", "HUMAN_GATE"):
                    continue

                # 4. Heavy job limit check
                if candidate.heavy_job and (active_heavy_jobs_count >= self.HEAVY_JOB_LIMIT):
                    continue

                # 5. Scope conflict check
                cand_scopes = set(candidate.allowed_scope or [candidate.project or "GLOBAL"])
                if any(s in occupied_scopes or s in assigned_scopes_this_cycle for s in cand_scopes):
                    continue

                # Safe candidate found!
                task_fp = hashlib.sha256(f"{candidate.opportunity_id}|{candidate.priority}|{json.dumps(sorted(list(cand_scopes)))}".encode()).hexdigest()[:16]

                recommendation = WorkerRecommendation(
                    worker_id=wid,
                    available=True,
                    safe_task_available=True,
                    task_id=candidate.opportunity_id,
                    task_fingerprint=task_fp,
                    scope=list(cand_scopes),
                    risk=candidate.risk,
                    heavy_job=candidate.heavy_job,
                    block_reason=None,
                    recommended_action=f"DISPATCH_TASK_{candidate.opportunity_id}",
                )
                recommendations[wid] = recommendation.to_dict()

                assigned_tasks_this_cycle.add(candidate.opportunity_id)
                for s in cand_scopes:
                    assigned_scopes_this_cycle.add(s)
                if candidate.heavy_job:
                    active_heavy_jobs_count += 1

                candidate_found = True
                self.telemetry["tasks_recommended"] += 1

                # Emit NEXT_SAFE_WORK_AVAILABLE event
                self._emit_next_safe_work_event(worker, candidate, task_fp)
                break

            if not candidate_found:
                recommendations[wid] = WorkerRecommendation(
                    worker_id=wid,
                    available=True,
                    safe_task_available=False,
                    block_reason="NO_SAFE_DISJOINT_TASK_AVAILABLE",
                    recommended_action="STANDBY_SAFE_IDLE",
                ).to_dict()

        result = {
            "schema_version": "3.0",
            "evaluated_at": utc_now(),
            "workers_evaluated_count": len(workers),
            "recommendations": recommendations,
            "tasks_assigned_count": len(assigned_tasks_this_cycle),
            "telemetry": self.telemetry,
        }

        # Content fingerprinting for write/alert deduplication
        content_hash = hashlib.sha256(json.dumps(recommendations, sort_keys=True).encode("utf-8")).hexdigest()
        if content_hash == self._last_recommendation_hash and self.output_file.exists():
            self.telemetry["duplicates_suppressed"] += 1
        else:
            safe_write_json(self.output_file, result)
            self._last_recommendation_hash = content_hash

        return result

    def _emit_next_safe_work_event(self, worker: WorkerRecord, task: Opportunity, task_fp: str) -> None:
        """Emits deduplicated NEXT_SAFE_WORK_AVAILABLE event to Chief/HQ alert feed."""
        ev_payload = {
            "worker_id": worker.worker_id,
            "task_id": task.opportunity_id,
            "priority": task.priority,
            "project": task.project,
            "task_fingerprint": task_fp,
        }
        fp = hashlib.sha256(f"{worker.worker_id}|{task.opportunity_id}|NEXT_SAFE_WORK_AVAILABLE|{task_fp}".encode()).hexdigest()[:16]

        event_id = f"evt-safe-{uuid.uuid4().hex[:10]}"
        event = {
            "schema_version": "3.0",
            "event_id": event_id,
            "event_type": "NEXT_SAFE_WORK_AVAILABLE",
            "worker_id": worker.worker_id,
            "task_id": task.opportunity_id,
            "fingerprint": fp,
            "severity": "INFO",
            "evidence": ev_payload,
            "recommended_action": f"CLAIM_OPPORTUNITY_{task.opportunity_id}",
            "created_at": utc_now(),
            "acknowledged": False,
        }
        safe_write_json(self.events_dir / f"{event_id}.json", event)


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic Next-Safe-Work Router")
    parser.add_argument("--route", action="store_true", help="Evaluate next safe work for available workers")
    args = parser.parse_args()

    router = NextSafeWorkRouter()
    res = router.evaluate_next_safe_work()
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
