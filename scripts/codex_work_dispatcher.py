#!/usr/bin/env python3
"""One clean Courier route: OpportunityQueue -> Router -> lease -> Codex result."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sys
import uuid
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(COURIER_DIR) not in sys.path:
    sys.path.insert(0, str(COURIER_DIR))

from scripts.canonical_authority import CanonicalAuthority
from scripts.live_worker_registry import LiveWorkerRegistry, WorkerState
from scripts.next_safe_work_router import NextSafeWorkRouter
from scripts.opportunity_queue import Opportunity, OpportunityQueue
from scripts.run_codex_bridge import CodexHookRunner, CodexVisualStateTracker, execute_codex_task

WINDOWS_SCOPE = r"C:\Dev\Windows-AI-OS"
WINDOWS_HOST = "DESKTOP-JDPRUGR"
OWNER = "agent-codex-bridge"


def stable_hash(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp.{os.getpid()}")
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def main() -> int:
    """Create exactly one fresh, router-selected, read-only Windows task."""
    registry = LiveWorkerRegistry(repo_dir=COURIER_DIR)
    registry.register_worker(worker_id="CODEX", role="specialist architecture", provider="local")
    worker = registry.get_worker("CODEX")
    if worker is None:
        raise RuntimeError("CODEX worker registration failed")
    worker.state = WorkerState.SAFE_IDLE.value
    registry._save_worker_record(worker)

    opportunity_id = f"OPP-CODEX-WINDOWS-{uuid.uuid4().hex[:12]}"
    queue = OpportunityQueue(repo_dir=COURIER_DIR)
    opportunity = Opportunity(
        opportunity_id=opportunity_id,
        source="COURIER_ROUTER",
        objective_id="OBJ-WINDOWS-AI-OS-FOUNDATION",
        project="WINDOWS_AI_OS",
        description="Read-only Windows project identity check.",
        priority=10,
        required_capabilities=["WINDOWS_EXECUTION"],
        risk="SAFE",
        estimated_cost=0.0,
        status="READY",
        target_agent=None,
        allowed_scope=[WINDOWS_SCOPE],
        allowed_actions=["READ"],
    )
    if not queue.add_opportunity(opportunity):
        raise RuntimeError("Fresh opportunity unexpectedly deduplicated")

    route = NextSafeWorkRouter(repo_dir=COURIER_DIR).evaluate_next_safe_work()
    recommendation = route.get("recommendations", {}).get("CODEX", {})
    if (
        recommendation.get("task_id") != opportunity_id
        or recommendation.get("target_host") != WINDOWS_HOST
        or not str(recommendation.get("recommended_action", "")).startswith("DISPATCH_TASK_")
    ):
        raise RuntimeError("Router did not select the fresh Windows opportunity")

    claimed, claim_state, claim = queue.claim_opportunity(opportunity_id, OWNER, lease_seconds=300)
    if not claimed:
        raise RuntimeError(f"Opportunity claim failed: {claim_state}")
    task_id = queue.canonical_task_id(opportunity_id, claim["state_version"])

    authority = CanonicalAuthority()
    acquired, generation, error = authority.acquire_scopes(
        owner_id=OWNER,
        task_id=task_id,
        scopes=[WINDOWS_SCOPE],
        ttl_seconds=300,
        metadata={"opportunity_id": opportunity_id, "router_event": "NEXT_SAFE_WORK_AVAILABLE"},
    )
    if not acquired:
        queue.release_opportunity_claim(opportunity_id, claim["claim_id"])
        raise RuntimeError(f"Scope lease failed: {error}")
    lease_path = authority._scope_file_path(WINDOWS_SCOPE)
    lease_record = json.loads(lease_path.read_text(encoding="utf-8"))

    opportunity_path = COURIER_DIR / "events" / "opportunity-queue" / f"{opportunity_id}.json"
    opportunity_record = json.loads(opportunity_path.read_text(encoding="utf-8"))
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    receipt_body = {
        "schema_version": "1.0",
        "artifact_type": "COURIER_ROUTED_DISPATCH_PROVENANCE",
        "origin": "COURIER_ROUTER",
        "source_agent": "COURIER_ROUTER",
        "task_id": task_id,
        "opportunity_id": opportunity_id,
        "goal_id": opportunity.objective_id,
        "target_agent": "CODEX",
        "target_host": WINDOWS_HOST,
        "project_path": WINDOWS_SCOPE,
        "scope": [WINDOWS_SCOPE],
        "route_action": recommendation["recommended_action"],
        "opportunity_sha256": stable_hash(opportunity_record),
        "created_at": now,
    }
    source_hash = stable_hash(receipt_body)
    receipt_path = COURIER_DIR / "events" / "receipts" / f"{task_id}-dispatch-provenance.json"
    atomic_write_json(receipt_path, {**receipt_body, "artifact_sha256": source_hash})

    envelope = {
        "task_id": task_id,
        "goal_id": opportunity.objective_id,
        "source_agent": "COURIER_ROUTER",
        "target_agent": "CODEX",
        "target_host": WINDOWS_HOST,
        "project_path": WINDOWS_SCOPE,
        "scope": [WINDOWS_SCOPE],
        "action": "Read-only Windows project identity check.",
        "status": "PENDING",
        "created_at": now,
        "provenance": {
            "origin": "COURIER_ROUTER",
            "task_identity": task_id,
            "source_artifact": str(receipt_path.relative_to(COURIER_DIR)),
            "source_sha256": source_hash,
        },
        "lease": {
            "authority": "CanonicalAuthority",
            "record_path": str(lease_path.relative_to(COURIER_DIR)),
            "record_sha256": stable_hash(lease_record),
            "owner_id": OWNER,
            "task_id": task_id,
            "scope": WINDOWS_SCOPE,
            "generation": generation,
            "lease_expires_at": lease_record["lease_expires_at"],
        },
        "payload": {"prompt": "Read-only Windows project identity check.", "allowed_scope": [WINDOWS_SCOPE]},
    }
    dispatch_path = COURIER_DIR / "events" / "dispatch" / f"{task_id}-worker-job.json"
    atomic_write_json(dispatch_path, envelope)

    result_path = execute_codex_task(
        dispatch_path, CodexHookRunner(CodexVisualStateTracker()), try_real_cli=False
    )
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("status") != "COMPLETED" or result.get("payload", {}).get("verdict") != "PASS":
        raise RuntimeError("Codex bridge did not produce a verified completed result")
    durable_result = {
        "schema_version": "1.0",
        "result_type": "LOCAL_VALIDATION_RESULT",
        "task_id": task_id,
        "opportunity_id": opportunity_id,
        "claim_id": claim["claim_id"],
        "generation": claim["state_version"],
        "status": "SUCCESS",
        "handler": "DETERMINISTIC_LOCAL_VALIDATION",
        "completed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "metadata": {"codex_result_path": str(result_path.relative_to(COURIER_DIR))},
    }
    durable_result["result_fingerprint"] = queue.expected_result_fingerprint(
        opportunity, claim, durable_result
    )
    if not queue.complete_claimed_opportunity(
        opportunity_id, claim["claim_id"], claim["state_version"], durable_result
    ):
        raise RuntimeError("Queue refused the fenced completion result")
    processed_job = COURIER_DIR / "events" / "processed" / dispatch_path.name
    if processed_job.exists():
        raise RuntimeError("Refusing to overwrite an existing processed dispatch record")
    os.replace(dispatch_path, processed_job)
    print(json.dumps({"task_id": task_id, "result_path": str(result_path.relative_to(COURIER_DIR))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
