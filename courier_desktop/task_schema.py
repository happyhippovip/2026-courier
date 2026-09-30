"""Desktop overlay: Task/Result parcel schema and claiming.

Parcels are the visible slips the blue Courier carries: a TaskParcel shows a
task_id, a ResultParcel shows a result_id. This module validates parcel
dicts and performs the claim transition. It never touches agent execution;
it only describes and validates parcels.
"""

from __future__ import annotations

from pathlib import Path, PureWindowsPath
from typing import Any

TASK_STATUSES = ("NEW", "CLAIMED", "RUNNING", "BLOCKED", "DONE", "FAILED")
RESULT_STATUSES = ("READY", "APPROVED", "REJECTED")

TASK_IDENTITY_FIELDS = ("goal_id", "task_id", "attempt_id", "dispatch_id")
RESULT_IDENTITY_FIELDS = ("result_id", "task_id", "dispatch_id")

_CLAIMABLE_FROM = ("NEW",)


def _require_str(record: dict[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value or len(value) > 128:
        raise ValueError(f"parcel field {field!r} must be a non-empty string (<=128)")
    return value


def _check_artifact_path(path: Any) -> str:
    if not isinstance(path, str) or not path or Path(path).is_absolute() or ".." in Path(path).parts:
        raise ValueError("unsafe artifact path")
    windows = PureWindowsPath(path)
    if windows.drive or windows.root or ".." in windows.parts:
        raise ValueError("unsafe artifact path")
    return path


def validate_task_parcel(parcel: dict[str, Any]) -> dict[str, Any]:
    """Fail closed unless the dict is a well-formed TaskParcel."""
    if not isinstance(parcel, dict):
        raise ValueError("TaskParcel must be a JSON object")
    for field in TASK_IDENTITY_FIELDS:
        _require_str(parcel, field)
    status = _require_str(parcel, "status")
    if status not in TASK_STATUSES:
        raise ValueError(f"unknown task status {status!r}")
    title = parcel.get("title", "")
    if not isinstance(title, str) or len(title) > 256:
        raise ValueError("parcel field 'title' must be a string (<=256)")
    return parcel


def validate_result_parcel(parcel: dict[str, Any]) -> dict[str, Any]:
    """Fail closed unless the dict is a well-formed ResultParcel."""
    if not isinstance(parcel, dict):
        raise ValueError("ResultParcel must be a JSON object")
    for field in RESULT_IDENTITY_FIELDS:
        _require_str(parcel, field)
    status = _require_str(parcel, "status")
    if status not in RESULT_STATUSES:
        raise ValueError(f"unknown result status {status!r}")
    artifacts = parcel.get("artifacts", [])
    if not isinstance(artifacts, list):
        raise ValueError("parcel field 'artifacts' must be a list")
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise ValueError("unsafe artifact path")
        _check_artifact_path(artifact.get("path", ""))
        digest = artifact.get("sha256", "")
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("invalid artifact fingerprint")
    return parcel


def claim_task(parcel: dict[str, Any], worker_id: str) -> dict[str, Any]:
    """Move a NEW TaskParcel to CLAIMED for worker_id. Returns a new dict."""
    validate_task_parcel(parcel)
    if not isinstance(worker_id, str) or not worker_id or len(worker_id) > 128:
        raise ValueError("worker_id must be a non-empty string (<=128)")
    if parcel["status"] not in _CLAIMABLE_FROM:
        raise ValueError(f"task {parcel['task_id']!r} is not claimable from {parcel['status']!r}")
    claimed = dict(parcel)
    claimed["status"] = "CLAIMED"
    claimed["worker_id"] = worker_id
    return claimed
