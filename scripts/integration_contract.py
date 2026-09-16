"""Canonical TaskPacket/DurableResult glue for the multi-worker control plane.

Workers may have platform-specific payloads, but the control plane owns the
workflow identity and independently binds an observed effect to that identity.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path


TASK_STATES = {
    "QUEUED",
    "DISPATCHED",
    "RESULT_RECEIVED",
    "RECONCILED",
    "FAILED_VERIFICATION",
    "FAILED_TERMINAL",
    "HUMAN_REQUIRED",
}
RESULT_STATES = {"SUCCESS", "FAILED", "AUTH_REQUIRED"}
WORKER_IDS = {
    "github": "GITHUB-HOSTED",
    "mac": "MAC-01",
    "windows": "WINDOWS-01",
    "linux": "AWS-LINUX-01",
}


class ContractError(ValueError):
    """The worker envelope cannot be bound to the dispatched task."""


def _canonical_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def prepare_task(task: dict) -> dict:
    """Add stable workflow identity before the task is durably dispatched."""
    packet = dict(task)
    task_id = packet.get("task_id")
    goal_id = packet.get("goal_id")
    capability = packet.get("target_capability")
    if not all(isinstance(value, str) and value for value in (task_id, goal_id, capability)):
        raise ContractError("task_id, goal_id and target_capability are required")
    if capability not in WORKER_IDS:
        raise ContractError(f"unsupported target_capability: {capability}")

    packet.setdefault("attempt_id", f"{task_id}:attempt:1")
    packet.setdefault("dispatch_id", f"dispatch-{uuid.uuid4().hex}")
    packet.setdefault("worker_id", WORKER_IDS[capability])
    packet.setdefault("run_id", None)
    packet.setdefault("result_id", None)
    packet.setdefault("artifacts", [f"courier_canary_{task_id}.txt"])
    packet.setdefault("status", "QUEUED")
    if packet["status"] not in TASK_STATES:
        raise ContractError(f"invalid task status: {packet['status']}")
    return packet


def verify_result(task: dict, raw_result: dict, workspace: Path) -> dict:
    """Return a canonical DurableResult only after identity/effect verification."""
    for field in ("goal_id", "task_id", "attempt_id", "dispatch_id", "worker_id"):
        if not task.get(field):
            raise ContractError(f"dispatched task is missing {field}")

    if raw_result.get("goal_id") != task["goal_id"]:
        raise ContractError("goal_id mismatch")
    if raw_result.get("task_id") != task["task_id"]:
        raise ContractError("task_id mismatch")
    if raw_result.get("worker_id") != task["worker_id"]:
        raise ContractError("worker_id mismatch")
    if raw_result.get("status") not in RESULT_STATES:
        raise ContractError("invalid result status")

    run_id = raw_result.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise ContractError("observable run_id is required")

    artifacts = []
    if raw_result["status"] == "SUCCESS":
        expected = task.get("artifacts")
        if not isinstance(expected, list) or not expected:
            raise ContractError("successful task has no expected artifacts")
        for relative_name in expected:
            if not isinstance(relative_name, str) or Path(relative_name).is_absolute() or ".." in Path(relative_name).parts:
                raise ContractError("unsafe artifact path")
            artifact_path = workspace / relative_name
            if not artifact_path.is_file():
                raise ContractError(f"missing expected artifact: {relative_name}")
            artifacts.append(
                {
                    "path": relative_name,
                    "sha256": hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
                }
            )

    identity = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "run_id": run_id,
        "status": raw_result["status"],
        "artifacts": artifacts,
    }
    
    if raw_result["status"] != "SUCCESS":
        for field in ["raw_diagnostic", "stderr", "reason"]:
            if field in raw_result:
                identity[field] = raw_result[field]
                
    identity["result_id"] = f"result-{_canonical_hash(identity)}"
    return identity


def validate_durable_result(task: dict, result: dict) -> dict:
    """Validate a remote DurableResult without trusting worker-only success.

    This validates identity and evidence shape. A separate verifier must still
    observe the effect and approve the evidence before workflow advancement.
    """
    required = {
        "goal_id",
        "task_id",
        "attempt_id",
        "dispatch_id",
        "worker_id",
        "run_id",
        "result_id",
        "status",
        "artifacts",
    }
    missing = sorted(required - set(result))
    if missing:
        raise ContractError(f"result is missing: {', '.join(missing)}")
    for field in ("goal_id", "task_id", "attempt_id", "dispatch_id", "worker_id"):
        if result[field] != task.get(field):
            raise ContractError(f"{field} mismatch")
    for field in ("run_id", "result_id"):
        if not isinstance(result[field], str) or not result[field]:
            raise ContractError(f"{field} is required")
    if result["status"] not in RESULT_STATES:
        raise ContractError("invalid result status")
    if not isinstance(result["artifacts"], list):
        raise ContractError("artifacts must be a list")
    if result["status"] == "SUCCESS" and not result["artifacts"]:
        raise ContractError("successful result requires artifact evidence")
    for artifact in result["artifacts"]:
        if not isinstance(artifact, dict) or set(artifact) != {"path", "sha256"}:
            raise ContractError("invalid artifact evidence")
        path = artifact["path"]
        digest = artifact["sha256"]
        if not isinstance(path, str) or not path or Path(path).is_absolute() or ".." in Path(path).parts:
            raise ContractError("unsafe artifact path")
        if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ContractError("invalid artifact fingerprint")
    return {field: result[field] for field in required}
