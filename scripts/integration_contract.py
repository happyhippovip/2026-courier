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


SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def validate_safe_id(ident: str, field_name: str = "identifier") -> str:
    if not isinstance(ident, str) or not ident:
        raise ContractError(f"{field_name} is required and must be a non-empty string")
    if not SAFE_ID_RE.match(ident) or ".." in ident or "/" in ident or "\\" in ident:
        raise ContractError(f"{field_name} contains forbidden characters or path traversal: {ident!r}")
    return ident


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
    "antigravity": "ANTIGRAVITY-POOL",
    "generic": "GENERIC-ROUTER",
}


MAX_BODY_BYTES = 1024 * 1024  # 1 MiB wire limit for JSON payloads
MAX_ARTIFACTS = 64  # max artifacts per result
MAX_ARTIFACT_BYTES = 16 * 1024 * 1024  # 16 MiB max per artifact and total artifact set


class ContractError(ValueError):
    """The worker envelope cannot be bound to the dispatched task."""


def _canonical_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def normalize_target_capability(target: str) -> str:
    """Normalize target capability while strictly separating platform from provider.

    Decoupled Contract (CP-16):
    - Antigravity is an agent provider/runtime, NOT an OS requirement.
    - Generic tasks are platform-neutral.
    - Strict OS targets (windows, mac, linux) remain strictly bounded.
    """
    target_lower = str(target or "").lower().strip()
    if "github" in target_lower:
        return "github"
    if "antigravity" in target_lower:
        return "antigravity"
    if "windows" in target_lower:
        return "windows"
    if "mac" in target_lower or "darwin" in target_lower:
        return "mac"
    if "linux" in target_lower:
        return "linux"
    if target_lower in ("generic", "any", "neutral", "all", "python", "deterministic", ""):
        return "generic"
    raise ContractError(f"unsupported target_capability: {target}")


def prepare_task(task: dict) -> dict:
    """Add stable workflow identity before the task is durably dispatched."""
    packet = dict(task)
    task_id = packet.get("task_id")
    goal_id = packet.get("goal_id")
    raw_cap = packet.get("target_capability") or packet.get("target_agent")
    if not raw_cap:
        raise ContractError("task_id, goal_id and target_capability are required")
    capability = normalize_target_capability(raw_cap)
    packet["target_capability"] = capability
    packet["target_agent"] = capability
    validate_safe_id(task_id, "task_id")
    validate_safe_id(goal_id, "goal_id")
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
    if bool(packet.get("unknown_cost")):
        packet["estimated_cost_eur"] = None
    else:
        packet.setdefault("estimated_cost_eur", 0.0)
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

    # Optional fields (workkey, source_sha, input_fingerprint, action, test_result, next_action): must not be invented; if present on either, must match exactly
    for field in ("workkey", "source_sha", "input_fingerprint", "action", "test_result", "next_action"):
        task_val = task.get(field)
        res_val = raw_result.get(field)
        if task_val is not None:
            if res_val is not None and res_val != task_val:
                raise ContractError(f"{field} mismatch")
        elif res_val is not None:
            raise ContractError(f"{field} invented on result")

    if "owner" in task or "owner" in raw_result:
        owner_task = task.get("owner")
        owner_res = raw_result.get("owner")
        if owner_task is not None:
            if "owner" in raw_result and owner_res != owner_task:
                raise ContractError("owner mismatch")
        elif owner_res is not None:
            raise ContractError("owner mismatch")

    if raw_result.get("status") not in RESULT_STATES:
        raise ContractError("invalid result status")

    run_id = raw_result.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise ContractError("observable run_id is required")

    # Guard against execution-ID confusion: run_id must be distinct from dispatch/attempt/task/goal/worker IDs
    if run_id == raw_result.get("dispatch_id"):
        raise ContractError("run_id must not equal dispatch_id")
    if run_id == raw_result.get("attempt_id"):
        raise ContractError("run_id must not equal attempt_id")
    if run_id == raw_result.get("task_id"):
        raise ContractError("run_id must not equal task_id")
    if run_id == raw_result.get("goal_id"):
        raise ContractError("run_id must not equal goal_id")
    if run_id == raw_result.get("worker_id"):
        raise ContractError("run_id must not equal worker_id")

    # If task already specifies a bound run_id, result run_id must match exactly
    task_run_id = task.get("run_id")
    if task_run_id is not None and run_id != task_run_id:
        raise ContractError("run_id mismatch")

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
    if "workkey" in task:
        identity["workkey"] = task["workkey"]
    if "source_sha" in task:
        identity["source_sha"] = task["source_sha"]
    for field in ("input_fingerprint", "action", "test_result", "next_action"):
        if field in task and field not in identity:
            identity[field] = task[field]
        elif field in raw_result and field not in identity:
            identity[field] = raw_result[field]
    if "owner" in task or "owner" in raw_result:
        identity["owner"] = raw_result.get("owner") or task.get("owner") or task["worker_id"]
    computed_result_id = f"result-{_canonical_hash(identity)}"
    provided_result_id = raw_result.get("result_id")
    if provided_result_id is not None and provided_result_id != computed_result_id:
        raise ContractError("result_id mismatch")
    identity["result_id"] = computed_result_id
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
        "source_sha",
    }
    # GitHub Actions supplies a retry-generation identity in addition to run_id.
    # Preserve it when provided so a DurableResult remains bound to the exact run.
    if "run_attempt" in result:
        required.add("run_attempt")
    # Preserve and enforce optional bound identity & lifecycle checkpoint fields when declared
    for field in (
        "workkey",
        "source_sha",
        "input_fingerprint",
        "action",
        "test_result",
        "next_action",
    ):
        task_val = task.get(field)
        res_val = result.get(field)
        if task_val is not None or res_val is not None:
            if res_val is not None and task_val is not None and res_val != task_val:
                raise ContractError(f"{field} mismatch")
            if res_val is not None:
                required.add(field)
            elif task_val is not None:
                result[field] = task_val
                required.add(field)

    if "owner" in task or "owner" in result:
        owner_task = task.get("owner")
        owner_res = result.get("owner")
        if owner_task is not None:
            if "owner" in result and owner_res != owner_task:
                raise ContractError("owner mismatch")
            result["owner"] = owner_task
            required.add("owner")
        elif owner_res is not None:
            raise ContractError("owner mismatch")

    missing = sorted(required - set(result))
    if missing:
        raise ContractError(f"result is missing: {', '.join(missing)}")
    if not isinstance(result.get("source_sha"), str) or not re.fullmatch(r"[0-9a-f]{40}", result["source_sha"]):
        raise ContractError("source_sha is required")
    for field in ("goal_id", "task_id", "attempt_id", "dispatch_id", "worker_id"):
        if result[field] != task.get(field):
            raise ContractError(f"{field} mismatch")
    if "attempt" in result:
        if isinstance(result["attempt"], bool) or not isinstance(result["attempt"], int) or result["attempt"] < 1:
            raise ContractError("attempt must be an integer >= 1")
        task_attempts = task.get("attempts", task.get("attempt"))
        if task_attempts is not None and result["attempt"] != task_attempts:
            raise ContractError("attempt mismatch")
        required.add("attempt")
    for field in ("run_id", "result_id"):
        if not isinstance(result[field], str) or not result[field]:
            raise ContractError(f"{field} is required")
    if (
        not isinstance(result["result_id"], str)
        or not re.fullmatch(r"(?:result|res)-[A-Za-z0-9_.:-]{1,128}", result["result_id"])
        or ".." in result["result_id"]
    ):
        raise ContractError("invalid result_id format")
    for field in ("run_id", "dispatch_id", "attempt_id", "task_id", "goal_id", "worker_id"):
        if result["result_id"] == result.get(field):
            raise ContractError(f"result_id must not equal {field}")
    if result["run_id"] == result.get("dispatch_id"):
        raise ContractError("run_id must not equal dispatch_id")
    if result["run_id"] == result.get("attempt_id"):
        raise ContractError("run_id must not equal attempt_id")
    if result["run_id"] == result.get("task_id"):
        raise ContractError("run_id must not equal task_id")
    if result["run_id"] == result.get("goal_id"):
        raise ContractError("run_id must not equal goal_id")
    if result["run_id"] == result.get("worker_id"):
        raise ContractError("run_id must not equal worker_id")
    if task.get("run_id") is not None and result["run_id"] != task["run_id"]:
        raise ContractError("run_id mismatch")
    if "run_attempt" in required and (not isinstance(result["run_attempt"], str) or not result["run_attempt"].isdigit()):
        raise ContractError("run_attempt is invalid")
    if result["status"] not in RESULT_STATES:
        raise ContractError("invalid result status")
    if not isinstance(result["artifacts"], list):
        raise ContractError("artifacts must be a list")
    if len(result["artifacts"]) > MAX_ARTIFACTS:
        raise ContractError(f"artifacts count exceeds limit of {MAX_ARTIFACTS}")
    if result["status"] == "SUCCESS" and not result["artifacts"]:
        raise ContractError("successful result requires artifact evidence")
    total_artifact_size = 0
    for artifact in result["artifacts"]:
        # Uploaded artifacts additionally carry the server-issued artifact_id and size.
        if not isinstance(artifact, dict) or set(artifact) not in ({"path", "sha256"},
                                                                   {"path", "sha256", "size"},
                                                                   {"path", "sha256", "artifact_id", "size"}):
            raise ContractError("invalid artifact evidence")
        if "artifact_id" in artifact:
            if not isinstance(artifact["artifact_id"], str) or not re.fullmatch(r"art-[a-f0-9]{64}", artifact["artifact_id"]):
                raise ContractError("invalid artifact_id")
            if not isinstance(artifact["size"], int) or isinstance(artifact["size"], bool) or artifact["size"] < 0:
                raise ContractError("invalid artifact size")
            if artifact["size"] > MAX_ARTIFACT_BYTES:
                raise ContractError("artifact exceeds size limit")
            total_artifact_size += artifact["size"]
        elif "size" in artifact:
            if not isinstance(artifact["size"], int) or isinstance(artifact["size"], bool) or artifact["size"] < 0:
                raise ContractError("invalid artifact size")
            if artifact["size"] > MAX_ARTIFACT_BYTES:
                raise ContractError("artifact exceeds size limit")
            total_artifact_size += artifact["size"]
        path = artifact["path"]
        digest = artifact["sha256"]
        if not isinstance(path, str) or not path or Path(path).is_absolute() or ".." in Path(path).parts:
            raise ContractError("unsafe artifact path")
        windows = PureWindowsPath(path)
        if windows.drive or windows.root or ".." in windows.parts:
            raise ContractError("unsafe artifact path")
        if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ContractError("invalid artifact fingerprint")
    if total_artifact_size > MAX_ARTIFACT_BYTES:
        raise ContractError("total artifact size exceeds limit")
    return {field: result[field] for field in required}


def persist_durable_receipt(task: dict, result: dict, receipt_dir: Path) -> Path:
    """Atomically persist a verified durable result as a canonical receipt file.

    Returns the receipt Path. A duplicate write of identical content succeeds
    idempotently (ACK_DUPLICATE semantics), while conflicting content for the same
    receipt identity raises ContractError.
    """
    valid = validate_durable_result(task, result)
    receipt_dir = Path(receipt_dir)
    receipt_dir.mkdir(parents=True, exist_ok=True)

    # Deterministic receipt identity
    result_clean = valid["result_id"].replace("result-", "")[:16]
    receipt_id = f"rcpt-{result_clean}"
    target = receipt_dir / f"{receipt_id}.json"

    # Canonical receipt structure
    receipt_body = dict(valid)
    receipt_body["receipt_id"] = receipt_id
    receipt_body["schema_version"] = "2.0"
    receipt_body["receipt_hash"] = _canonical_hash(receipt_body)

    if target.exists():
        try:
            existing = json.loads(target.read_text(encoding="utf-8"))
            if existing == receipt_body:
                return target
        except Exception:
            pass
        raise ContractError("Conflicting result for already processed task")

    for existing_file in receipt_dir.glob("rcpt-*.json"):
        try:
            existing = json.loads(existing_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(existing, dict) and existing.get("task_id") == valid["task_id"]:
            if existing == receipt_body:
                return existing_file
            raise ContractError("Conflicting result for already processed task")

    temp_file = receipt_dir / f".tmp-{uuid.uuid4().hex}-{target.name}"
    content = json.dumps(receipt_body, indent=2, sort_keys=True) + "\n"
    temp_file.write_text(content, encoding="utf-8")
    temp_file.replace(target)
    return target


def load_durable_receipt(receipt_path: Path) -> dict:
    """Load and verify a durable receipt file from disk.

    Fails closed if the file is missing, corrupt, or fails cryptographic hash verification.
    """
    path = Path(receipt_path)
    if not path.is_file():
        raise ContractError(f"receipt file not found: {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ContractError(f"receipt is corrupt JSON: {exc.msg}")

    if not isinstance(data, dict):
        raise ContractError("receipt payload must be a JSON object")

    stored_hash = data.get("receipt_hash")
    if not isinstance(stored_hash, str) or not stored_hash:
        raise ContractError("receipt is missing receipt_hash")

    # Verify cryptographic integrity
    body = {k: v for k, v in data.items() if k != "receipt_hash"}
    expected_hash = _canonical_hash(body)
    if stored_hash != expected_hash:
        raise ContractError(f"receipt hash mismatch: expected {expected_hash}, got {stored_hash}")

    # Enforce receipt completeness
    mandatory = {
        "receipt_id",
        "schema_version",
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
    missing = sorted(mandatory - set(data))
    if missing:
        raise ContractError(f"receipt is incomplete, missing mandatory fields: {', '.join(missing)}")

    if not isinstance(data.get("receipt_id"), str) or not data["receipt_id"]:
        raise ContractError("receipt_id must be a non-empty string")
    if data.get("schema_version") != "2.0":
        raise ContractError(f"unsupported receipt schema_version: {data.get('schema_version')}")
    if data["status"] not in RESULT_STATES:
        raise ContractError(f"invalid receipt status: {data['status']}")
    if not isinstance(data["artifacts"], list):
        raise ContractError("receipt artifacts must be a list")
    if data["status"] == "SUCCESS" and not data["artifacts"]:
        raise ContractError("successful receipt requires artifact evidence")

    return data
