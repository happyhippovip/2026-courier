#!/usr/bin/env python3
"""Publish the Step-1 Google-to-Codex receiver envelope with canonical proof."""

import datetime
import hashlib
import json
import os
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(COURIER_DIR) not in sys.path:
    sys.path.insert(0, str(COURIER_DIR))

from scripts.canonical_authority import CanonicalAuthority
from scripts.live_worker_registry import LiveWorkerRegistry


def canonical_json_hash(payload: dict) -> str:
    """Stable binding hash for a machine-readable dispatch record."""
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def atomic_write_json(path: Path, payload: dict) -> None:
    """Publish JSON atomically so a receiver never reads a partial envelope."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp.{os.getpid()}")
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def main() -> int:
    task_id = "GOOGLE_TO_CODEX_HANDOFF_PROOF_20260914_RETRY1"
    objective_id = "OBJ-HANDOFF-1"
    scope = r"C:\Dev\Windows-AI-OS"
    task_hash = hashlib.sha256(f"CODEX_HANDOFF_{task_id}".encode()).hexdigest()[:16]

    # A completed result is immutable history.  Never republish the same
    # identity after it has reached a worker, even when its old envelope was
    # subsequently found invalid.  The orchestrator must issue a new ID.
    completed_result = COURIER_DIR / "events" / "processed" / f"{task_id}-result.json"
    if completed_result.exists():
        print(f"Refusing duplicate dispatch: completed result already exists for {task_id}")
        return 2

    registry = LiveWorkerRegistry(repo_dir=COURIER_DIR)
    registry.register_worker(worker_id="CODEX", role="specialist architecture", provider="local")
    worker = registry.get_worker("CODEX")
    if worker:
        worker.state = "SAFE_IDLE"
        registry._save_worker_record(worker)

    authority = CanonicalAuthority()
    acquired, generation, error = authority.acquire_scopes(
        owner_id="CODEX",
        task_id=task_id,
        scopes=[scope],
        ttl_seconds=300,
        metadata={"source_agent": "GOOGLE_ANTIGRAVITY", "purpose": "STEP_1_RECEIVER"},
    )
    if not acquired:
        print(f"Failed to acquire canonical scope authority: {error}")
        return 1

    authority_path = authority._scope_file_path(scope)
    authority_record = json.loads(authority_path.read_text(encoding="utf-8"))
    if (
        authority_record.get("owner_id") != "CODEX"
        or authority_record.get("task_id") != task_id
        or authority_record.get("scope") != scope
        or authority_record.get("generation") != generation
    ):
        raise RuntimeError("Canonical authority record is not bound to this task and scope")

    legacy_path = COURIER_DIR / "events" / "locks" / f"task_{task_id}.lease"
    if legacy_path.exists():
        legacy = json.loads(legacy_path.read_text(encoding="utf-8"))
        if legacy.get("task_id") != task_id or legacy.get("owner_id") != "CODEX":
            raise RuntimeError("Refusing to retire a lease not owned by this exact task")
        legacy_path.unlink()

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    receipt_body = {
        "schema_version": "1.0",
        "artifact_type": "COURIER_DISPATCH_PROVENANCE",
        "origin": "GOOGLE_ANTIGRAVITY",
        "source_agent": "GOOGLE_ANTIGRAVITY",
        "task_id": task_id,
        "task_hash": task_hash,
        "parent_task_id": "GOOGLE_TO_CODEX_HANDOFF_PROOF_20260914",
        "objective_id": objective_id,
        "target_agent": "CODEX",
        "target_host": "DESKTOP-JDPRUGR",
        "project_path": scope,
        "scope": [scope],
        "action": "Report remote project identity and one harmless project fact.",
        "created_at": now,
        "producer": "scripts/handoff_proof_step1_repair.py",
    }
    receipt_hash = canonical_json_hash(receipt_body)
    receipt_path = COURIER_DIR / "events" / "receipts" / f"{task_id}-dispatch-provenance.json"
    atomic_write_json(receipt_path, {**receipt_body, "artifact_sha256": receipt_hash})

    envelope = {
        "task_id": task_id,
        "goal_id": objective_id,
        "source_agent": "GOOGLE_ANTIGRAVITY",
        "target_agent": "CODEX",
        "target_host": "DESKTOP-JDPRUGR",
        "project_path": scope,
        "scope": [scope],
        "action": receipt_body["action"],
        "acceptance_criteria": "Return a valid JSON object with the expected task identity and safe summary.",
        "status": "PENDING",
        "created_at": now,
        "provenance": {
            "schema_version": "1.0",
            "origin": receipt_body["origin"],
            "task_identity": task_id,
            "parent_task_id": receipt_body["parent_task_id"],
            "objective_id": objective_id,
            "source_artifact": str(receipt_path.relative_to(COURIER_DIR)),
            "source_sha256": receipt_hash,
        },
        "lease": {
            "authority": "CanonicalAuthority",
            "record_path": str(authority_path.relative_to(COURIER_DIR)),
            "record_sha256": canonical_json_hash(authority_record),
            "owner_id": authority_record["owner_id"],
            "task_id": authority_record["task_id"],
            "scope": authority_record["scope"],
            "generation": authority_record["generation"],
            "lease_expires_at": authority_record["lease_expires_at"],
        },
        "task_hash": task_hash,
        "worker_id": "CODEX",
        "payload": {
            "prompt": receipt_body["action"],
            "allowed_scope": [scope],
            "requires_write": False,
        },
    }
    out_path = COURIER_DIR / "events" / "dispatch" / f"{task_id}-worker-job.json"
    atomic_write_json(out_path, envelope)
    print(f"Canonical Step-1 envelope published: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
