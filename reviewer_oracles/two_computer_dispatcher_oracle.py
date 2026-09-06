#!/usr/bin/env python3
"""Independent, local acceptance primitives for a two-computer dispatcher.

This is intentionally a reviewer oracle, not a dispatcher or transport.  It
contains no network listener, authentication flow, credential access, or model
invocation.  Google 161G must later be evaluated against these invariants.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath
from typing import Any


NODE_FIELDS = {
    "node_id", "hostname", "platform", "workspace_path", "status", "last_heartbeat",
    "capabilities", "resource_pool", "current_task_id", "current_lease_id",
    "current_file_scope", "heavy_job_active", "continuation_state", "last_result_id",
}
NODE_STATUSES = {
    "UNKNOWN", "IDLE", "READY", "ACTIVE", "BLOCKED", "RESOURCE_BLOCKED",
    "HUMAN_GATE", "HUNG", "OFFLINE",
}
CONFIGURED_POOLS = {"GOOGLE_PRO_POOL_1", "GOOGLE_PRO_POOL_2", "GOOGLE_PRO_POOL_3"}
RESULT_FIELDS = {
    "result_id", "task_id", "node_id", "lease_id", "status", "started_at",
    "finished_at", "files_changed", "checks_run", "summary", "next_state",
}
SENSITIVE_KEYS = ("password", "token", "cookie", "credential", "secret", "authorization")
SENSITIVE_VALUES = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9_]{16,}|eyJ\S+\.\S+\.\S+)\b")


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else None


def validate_node(node: dict[str, Any]) -> list[str]:
    errors = []
    missing = NODE_FIELDS - set(node)
    if missing:
        errors.append("missing fields: " + ",".join(sorted(missing)))
    if node.get("status") not in NODE_STATUSES:
        errors.append("invalid node status")
    if parse_timestamp(node.get("last_heartbeat")) is None:
        errors.append("malformed last_heartbeat")
    if not isinstance(node.get("capabilities"), list):
        errors.append("capabilities must be a list")
    if not isinstance(node.get("heavy_job_active"), bool):
        errors.append("heavy_job_active must be boolean")
    return errors


def validate_registry(nodes: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for node in nodes:
        node_id = node.get("node_id")
        if not isinstance(node_id, str) or not node_id:
            errors.append("missing node_id")
        elif node_id in seen:
            errors.append("duplicate node_id: " + node_id)
        else:
            seen.add(node_id)
        errors.extend(f"{node_id or 'UNKNOWN'}: {item}" for item in validate_node(node))
    return errors


def heartbeat_state(node: dict[str, Any], now: datetime, max_age_seconds: int = 90) -> str:
    heartbeat = parse_timestamp(node.get("last_heartbeat"))
    if heartbeat is None:
        return "UNKNOWN"
    if now - heartbeat > timedelta(seconds=max_age_seconds):
        return "OFFLINE"
    return str(node.get("status", "UNKNOWN"))


def normalize_scope(scope: str) -> str:
    if not isinstance(scope, str) or not scope or scope.startswith("/"):
        raise ValueError("scope must be a non-empty relative path")
    path = PurePosixPath(scope.rstrip("/"))
    if ".." in path.parts or "." in path.parts:
        raise ValueError("scope traversal or ambiguity rejected")
    return str(path)


def scopes_overlap(left: str, right: str) -> bool:
    left_normal = normalize_scope(left)
    right_normal = normalize_scope(right)
    return (
        left_normal == right_normal
        or left_normal.startswith(right_normal + "/")
        or right_normal.startswith(left_normal + "/")
    )


def task_fingerprint(task: dict[str, Any]) -> str:
    durable = {
        "task_id": task.get("task_id"),
        "scope": normalize_scope(task["file_scope"]),
        "payload": task.get("payload"),
    }
    return hashlib.sha256(json.dumps(durable, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def claim_lease_atomically(lease_dir: str, task_id: str, node_id: str, lease_id: str) -> bool:
    """A portable O_EXCL contract used by the acceptance race test."""
    path = os.path.join(lease_dir, task_id + ".lease")
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return False
    with os.fdopen(descriptor, "w", encoding="utf-8") as target:
        json.dump({"task_id": task_id, "node_id": node_id, "lease_id": lease_id}, target, sort_keys=True)
        target.flush()
        os.fsync(target.fileno())
    return True


def can_dispatch(node: dict[str, Any], task: dict[str, Any], active_scopes: list[str]) -> tuple[bool, str]:
    if heartbeat_state(node, datetime.now(timezone.utc)) in {"OFFLINE", "UNKNOWN"}:
        return False, "node unavailable"
    if node.get("status") in {"BLOCKED", "RESOURCE_BLOCKED", "HUMAN_GATE", "HUNG"}:
        return False, "node unavailable"
    pool = task.get("resource_pool")
    if pool not in CONFIGURED_POOLS or node.get("resource_pool") != pool:
        return False, "resource pool mismatch or unconfigured"
    if task.get("heavy", False) and node.get("heavy_job_active"):
        return False, "per-node heavy job limit"
    scope = normalize_scope(task["file_scope"])
    if any(scopes_overlap(scope, active) for active in active_scopes):
        return False, "file scope conflict"
    return True, "eligible"


def validate_result(result: dict[str, Any], active_lease: dict[str, Any]) -> list[str]:
    errors = []
    missing = RESULT_FIELDS - set(result)
    if missing:
        errors.append("missing result fields")
    for key in ("task_id", "node_id", "lease_id"):
        if result.get(key) != active_lease.get(key):
            errors.append("lease mismatch: " + key)
    if parse_timestamp(result.get("started_at")) is None or parse_timestamp(result.get("finished_at")) is None:
        errors.append("malformed result timestamp")
    return errors


def lease_recovery_action(lease: dict[str, Any], completed_task_ids: set[str], node_state: str, now: datetime) -> str:
    """Fail closed: an expired lease is never itself enough to redispatch work."""
    if lease.get("task_id") in completed_task_ids:
        return "COMPLETE_ALREADY_RECORDED"
    expires_at = parse_timestamp(lease.get("expires_at"))
    if expires_at is None:
        return "INSPECTION_REQUIRED"
    if expires_at > now:
        return "ACTIVE_LEASE"
    if node_state in {"UNKNOWN", "OFFLINE", "HUNG"}:
        return "INSPECTION_REQUIRED"
    return "RECOVERY_EVIDENCE_REQUIRED"


def validate_onboarding(node: dict[str, Any], expected_workspace: str, project_fingerprint: str, transport: dict[str, Any]) -> list[str]:
    errors = validate_node(node)
    if node.get("workspace_path") != expected_workspace:
        errors.append("workspace mismatch")
    if transport.get("project_fingerprint") != project_fingerprint:
        errors.append("project fingerprint mismatch")
    if transport.get("reachable") is not True or transport.get("result_return") is not True:
        errors.append("transport unavailable")
    return errors


def writable_workspaces_safe(node_a: dict[str, Any], node_b: dict[str, Any]) -> bool:
    """Two writable nodes must not directly share one live working directory."""
    return PathLike(node_a.get("workspace_path")) != PathLike(node_b.get("workspace_path"))


def PathLike(value: Any) -> str:
    return str(PurePosixPath(str(value))).rstrip("/")


def secret_free(value: Any) -> bool:
    if isinstance(value, dict):
        return all(not any(part in str(key).lower() for part in SENSITIVE_KEYS) and secret_free(child) for key, child in value.items())
    if isinstance(value, list):
        return all(secret_free(child) for child in value)
    return not isinstance(value, str) or SENSITIVE_VALUES.search(value) is None


def classify_transport(manifest: dict[str, Any]) -> str:
    """Never infer real cross-machine transport from a local two-node fixture."""
    if manifest.get("transport_verified") is True and manifest.get("authenticated_transport") is True:
        return "REAL_TWO_MACHINE_TRANSPORT"
    if manifest.get("transport_declared") is True:
        return "PARTIAL_TRANSPORT"
    return "LOCAL_SIMULATION_ONLY"
