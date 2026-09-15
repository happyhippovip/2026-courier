# SIMULATION / NON-PRODUCTION EVIDENCE
# THIS SCRIPT DEVIATES FROM COURIER V1 ARCHITECTURE AND WAS CREATED AS A SYNTHETIC OVERNIGHT TEST
#!/usr/bin/env python3
"""Minimal WINDOWS work dispatcher — wires NextSafeWorkRouter to mac_request_producer.

Reuses:
  - scripts/next_safe_work_router.py   (evaluate_next_safe_work, WorkerRecommendation)
  - scripts/live_worker_registry.py    (register_worker, transition_worker_to_available)
  - scripts/opportunity_queue.py       (Opportunity, OpportunityQueue)
  - scripts/mac_request_producer.py    (create_request — frozen V1 transport)

What it does (one shot):
  1. Registers WINDOWS_PC2 as an AVAILABLE worker in the live registry
     (idempotent — re-registration is safe; existing record is overwritten).
  2. Enqueues exactly ONE WINDOWS-targeted opportunity if none exists for the
     given task fingerprint (dedupe via dedupe_hash).
  3. Runs NextSafeWorkRouter.evaluate_next_safe_work() once.
  4. If the router returns a safe DISPATCH recommendation for WINDOWS_PC2,
     calls mac_request_producer.create_request() — the frozen V1 atomic SMB write.
  5. Prints the resulting request ID and exits.

No loops. No new transport. No new queue. No architecture changes.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(COURIER_DIR) not in sys.path:
    sys.path.insert(0, str(COURIER_DIR))

from scripts.live_worker_registry import (
    AvailabilityClass,
    LiveWorkerRegistry,
    WorkerState,
)
from scripts.opportunity_queue import Opportunity, OpportunityQueue
from scripts.next_safe_work_router import NextSafeWorkRouter
from scripts.mac_request_producer import create_request


WINDOWS_WORKER_ID = "WINDOWS_PC2"
TASK_OPPORTUNITY_ID = "WINDOWS-RELAY-CONNECTIVITY-VALIDATION"


def _ensure_windows_worker(registry: LiveWorkerRegistry) -> None:
    """Register WINDOWS_PC2 as AVAILABLE if not already live."""
    workers = registry.list_workers()
    existing = workers.get(WINDOWS_WORKER_ID)
    if existing and existing.state == WorkerState.AVAILABLE.value and not existing.is_expired():
        print(f"[dispatcher] Worker {WINDOWS_WORKER_ID} already AVAILABLE — skipping re-registration.")
        return

    record = registry.register_worker(
        worker_id=WINDOWS_WORKER_ID,
        role="WINDOWS_RELAY_VALIDATOR",
        provider="WINDOWS",
        availability_class=AvailabilityClass.TEMPORARY_30_DAY,
        mutable_scope=["SAFE_LOCAL_VALIDATION"],
    )
    # register_worker leaves state=STARTING; advance to AVAILABLE directly
    record.state = WorkerState.AVAILABLE.value
    registry._save_worker_record(record)
    print(f"[dispatcher] Registered + set AVAILABLE: {WINDOWS_WORKER_ID}")


def _ensure_windows_opportunity(queue: OpportunityQueue) -> None:
    """Add one WINDOWS-targeted READY opportunity if not already present."""
    description = "Validate Windows relay connectivity and return operational proof"
    dedupe_hash = hashlib.sha256(
        f"{TASK_OPPORTUNITY_ID}:{description}".encode()
    ).hexdigest()[:16]

    existing = queue.opportunities.get(TASK_OPPORTUNITY_ID)
    if existing and existing.status in ("READY", "RUNNING"):
        print(f"[dispatcher] Opportunity {TASK_OPPORTUNITY_ID} already {existing.status} — skipping.")
        return

    opp = Opportunity(
        opportunity_id=TASK_OPPORTUNITY_ID,
        source="WINDOWS_WORK_DISPATCHER",
        description=description,
        objective_id="OBJ-WINDOWS-RELAY-01",
        project="COURIER_V1_RELAY",
        priority=7,
        risk="LOW",
        estimated_cost=0.0,
        heavy_job=False,
        status="READY",
        target_agent=WINDOWS_WORKER_ID,
        allowed_scope=["SAFE_LOCAL_VALIDATION"],
        dedupe_hash=dedupe_hash,
    )
    queue.add_opportunity(opp)
    print(f"[dispatcher] Enqueued opportunity: {TASK_OPPORTUNITY_ID}")


def dispatch_one_windows_task() -> str:
    """Returns the new REQ-MAC-* request ID, or raises on any failure."""
    repo_dir = COURIER_DIR

    registry = LiveWorkerRegistry(repo_dir=repo_dir)
    queue = OpportunityQueue(repo_dir=repo_dir)

    _ensure_windows_worker(registry)
    _ensure_windows_opportunity(queue)

    router = NextSafeWorkRouter(repo_dir=repo_dir)
    result = router.evaluate_next_safe_work()

    recs = result.get("recommendations", {})
    windows_rec = recs.get(WINDOWS_WORKER_ID, {})

    if not windows_rec.get("safe_task_available"):
        block = windows_rec.get("block_reason", "UNKNOWN")
        raise RuntimeError(
            f"Router did not produce a safe WINDOWS recommendation. "
            f"block_reason={block}  full_rec={json.dumps(windows_rec, indent=2)}"
        )

    task_id = windows_rec.get("task_id")
    task_fp = windows_rec.get("task_fingerprint")
    print(
        f"[dispatcher] Router recommendation: task_id={task_id}  "
        f"fingerprint={task_fp}  action={windows_rec.get('recommended_action')}"
    )

    # Frozen V1 atomic SMB write — no modification to mac_request_producer
    req_id = create_request()
    print(f"[dispatcher] Dispatched via V1 transport: {req_id}")
    return req_id


if __name__ == "__main__":
    try:
        req_id = dispatch_one_windows_task()
        print(f"
DISPATCHED_REQUEST_ID={req_id}")
        sys.exit(0)
    except Exception as exc:
        print(f"
DISPATCH_FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
