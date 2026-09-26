"""Canonical TaskPacket/DurableResult glue for the multi-worker control plane.

Workers may have platform-specific payloads, but the control plane owns the
workflow identity and independently binds an observed effect to that identity.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path, PureWindowsPath


TASK_STATES = {
    "QUEUED",
    "DISPATCHED",
    "RESULT_RECEIVED",
    "RECONCILED",
    "FAILED_VERIFICATION",
    "FAILED_TERMINAL",
    "HUMAN_REQUIRED",
}
RESULT_STATES = {"SUCCESS", "FAILED"}
WORKER_IDS = {
    "github": "GITHUB-HOSTED",
    "mac": "MAC-01",
    "windows": "WINDOWS-01",
    "linux": "AWS-LINUX-01",
    "antigravity": "MAC-01",
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

    for field in ("goal_id", "task_id", "attempt_id", "dispatch_id", "worker_id"):
        if raw_result.get(field) != task[field]:
            raise ContractError(f"{field} mismatch")
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
            if not isinstance(relative_name, str) or not relative_name:
                raise ContractError("unsafe artifact path")
            if Path(relative_name).is_absolute() or PureWindowsPath(relative_name).is_absolute() or bool(PureWindowsPath(relative_name).drive):
                raise ContractError("unsafe artifact path")
            if ".." in Path(relative_name).parts or ".." in PureWindowsPath(relative_name).parts:
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
    identity["result_id"] = f"result-{task['dispatch_id']}"
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
    # GitHub Actions supplies a retry-generation identity in addition to run_id.
    # Preserve it when provided so a DurableResult remains bound to the exact run.
    if "run_attempt" in result:
        required.add("run_attempt")
    missing = sorted(required - set(result))
    if missing:
        raise ContractError(f"result is missing: {', '.join(missing)}")
    for field in ("goal_id", "task_id", "attempt_id", "dispatch_id", "worker_id"):
        if result[field] != task.get(field):
            raise ContractError(f"{field} mismatch")
    for field in ("run_id", "result_id"):
        if not isinstance(result[field], str) or not result[field]:
            raise ContractError(f"{field} is required")
    if "run_attempt" in required and (not isinstance(result["run_attempt"], str) or not result["run_attempt"].isdigit()):
        raise ContractError("run_attempt is invalid")
    if result["status"] not in RESULT_STATES:
        raise ContractError("invalid result status")
    if not isinstance(result["artifacts"], list):
        raise ContractError("artifacts must be a list")
    if result["status"] == "SUCCESS" and not result["artifacts"]:
        raise ContractError("successful result requires artifact evidence")
    for artifact in result["artifacts"]:
        # Uploaded artifacts additionally carry the server-issued artifact_id and size.
        if not isinstance(artifact, dict) or set(artifact) not in ({"path", "sha256"},
                                                                   {"path", "sha256", "artifact_id", "size"}):
            raise ContractError("invalid artifact evidence")
        if "artifact_id" in artifact:
            if not isinstance(artifact["artifact_id"], str) or not re.fullmatch(r"art-[a-f0-9]{64}", artifact["artifact_id"]):
                raise ContractError("invalid artifact_id")
            if not isinstance(artifact["size"], int) or isinstance(artifact["size"], bool) or artifact["size"] < 0:
                raise ContractError("invalid artifact size")
        path = artifact["path"]
        digest = artifact["sha256"]
        if not isinstance(path, str) or not path:
            raise ContractError("unsafe artifact path")
        if Path(path).is_absolute() or PureWindowsPath(path).is_absolute() or bool(PureWindowsPath(path).drive):
            raise ContractError("unsafe artifact path")
        if ".." in Path(path).parts or ".." in PureWindowsPath(path).parts:
            raise ContractError("unsafe artifact path")
        windows = PureWindowsPath(path)
        if windows.drive or windows.root or ".." in windows.parts:
            raise ContractError("unsafe artifact path")
        if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ContractError("invalid artifact fingerprint")
    return {field: result[field] for field in required}
