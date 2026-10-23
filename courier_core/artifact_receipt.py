"""Artifact Receipt & Integrity Verification (User-Visible Proof).

Implements User Requirement 02:
Translates authoritative artifact records and verification state into both a
cryptographically sound machine-readable receipt and a human-readable proof
suitable for user presentation without leaking raw internal stack traces or secrets.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ARTIFACT_ID_RE = re.compile(r"^art-[0-9a-f]{64}$")

STATUS_VERIFIED_MATCH = "VERIFIED_MATCH"
STATUS_EXTERNAL_PRODUCED = "EXTERNAL_PRODUCED"
STATUS_HASH_MISMATCH = "HASH_MISMATCH"
STATUS_MISSING_DATA = "MISSING_DATA"

VALID_INTEGRITY_STATUSES = {
    STATUS_VERIFIED_MATCH,
    STATUS_EXTERNAL_PRODUCED,
    STATUS_HASH_MISMATCH,
    STATUS_MISSING_DATA,
}


def format_size(size_bytes: int | float | None) -> str:
    """Formats byte counts into a readable string (e.g. 42.5 KB)."""
    if isinstance(size_bytes, bool) or size_bytes is None:
        return "unknown"
    try:
        size = float(size_bytes)
    except (TypeError, ValueError):
        return "unknown"

    if size < 0:
        return "unknown"
    if size < 1024:
        return f"{int(size)} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.1f} GB"


def format_fingerprint(sha256_hex: str | None) -> str:
    """Formats 64-char hex SHA256 into shortened abcd1234...ef567890."""
    if not isinstance(sha256_hex, str) or not SHA256_RE.match(sha256_hex):
        return "unknown"
    return f"{sha256_hex[:8]}...{sha256_hex[-8:]}"


def _accepted_proof(task: Mapping[str, Any] | None) -> bool:
    """Verdict PASS and resolution verified. The caller still has to hash the bytes."""
    if not isinstance(task, Mapping):
        return False
    verification = task.get("verification")
    if not isinstance(verification, dict):
        return False
    return verification.get("verdict") == "PASS" and verification.get("resolution") == "verified"


def derive_integrity_status(
    record: Mapping[str, Any] | None,
    task: Mapping[str, Any] | None = None,
    blob_bytes: bytes | None = None,
) -> str:
    """Derive the deterministic integrity status of an artifact."""
    if not record:
        return STATUS_MISSING_DATA

    record_sha = record.get("sha256")
    if not isinstance(record_sha, str) or not SHA256_RE.match(record_sha):
        return STATUS_MISSING_DATA

    bytes_match = False
    if blob_bytes is not None:
        if isinstance(blob_bytes, str) or not isinstance(blob_bytes, (bytes, bytearray)):
            return STATUS_MISSING_DATA
        actual_sha = hashlib.sha256(blob_bytes).hexdigest()
        if actual_sha != record_sha:
            return STATUS_HASH_MISMATCH
        record_size = record.get("size")
        if isinstance(record_size, bool) or (record_size is not None and len(blob_bytes) != record_size):
            return STATUS_HASH_MISMATCH
        bytes_match = True

    if task:
        expected_sha = task.get("expected_sha256")
        if isinstance(expected_sha, str) and expected_sha and expected_sha != record_sha:
            return STATUS_HASH_MISMATCH

    # VERIFIED requires the hashed bytes and an accepted resolution.
    # A FAIL verdict is not rewritten into a hash mismatch when the bytes match.
    if not bytes_match or not _accepted_proof(task):
        return STATUS_MISSING_DATA
    if isinstance(task, Mapping) and task.get("source") in ("external", "ci", "github", "adapter_unbound"):
        return STATUS_EXTERNAL_PRODUCED
    return STATUS_VERIFIED_MATCH


def generate_artifact_receipt(
    artifact_id: str,
    *,
    store: Any = None,
    record: Mapping[str, Any] | None = None,
    task: Mapping[str, Any] | None = None,
    blob_bytes: bytes | None = None,
    download_base_url: str = "/artifacts",
    include_local_path: bool = True,
) -> dict[str, Any]:
    """Generates both machine-readable and human-readable receipt for an artifact.
    
    Guarantees:
    - Never leaks internal stack traces or server absolute private secrets.
    - Deterministic size and fingerprint formatting.
    - Verified cryptographic match checking.
    """
    if record is None and store is not None:
        try:
            record = store.get_record(artifact_id)
        except Exception:
            record = None

    if record is None:
        return {
            "artifact_id": artifact_id,
            "name": "unknown",
            "size_bytes": 0,
            "size_formatted": "unknown",
            "sha256": "unknown",
            "sha256_fingerprint": "unknown",
            "integrity_status": STATUS_MISSING_DATA,
            "is_valid": False,
            "verification_verdict": "FAIL",
            "provenance": {
                "task_id": (task or {}).get("task_id"),
                "goal_id": (task or {}).get("goal_id"),
                "worker_id": None,
                "dispatch_id": None,
                "attempt_id": None,
                "branch": None,
                "source_sha": None,
            },
            "human_summary": f"Artifact '{artifact_id}' could not be located in storage.",
            "file_access": {
                "download_url": f"{download_base_url}/{artifact_id}",
                "local_path": None,
            },
        }

    name = str(record.get("name", "unnamed_artifact"))
    size = record.get("size")
    size_fmt = format_size(size)
    sha256_hex = str(record.get("sha256", ""))
    fingerprint = format_fingerprint(sha256_hex)

    # If blob_bytes not passed, try to verify against store if possible
    if blob_bytes is None and store is not None:
        try:
            blob_bytes = store.read_bytes(artifact_id)
        except Exception:
            blob_bytes = None

    integrity_status = derive_integrity_status(record, task, blob_bytes=blob_bytes)
    is_valid = integrity_status in (STATUS_VERIFIED_MATCH, STATUS_EXTERNAL_PRODUCED)

    # Local path resolution (sanitized relative path in store)
    local_path = None
    if include_local_path and store is not None and hasattr(store, "_blob_path"):
        try:
            p = store._blob_path(sha256_hex)
            if p.exists():
                local_path = str(p)
        except Exception:
            local_path = None

    task_dict = task or {}
    verification = task_dict.get("verification")
    claimed = verification.get("verdict") if isinstance(verification, dict) else None
    resolution = verification.get("resolution") if isinstance(verification, dict) else None
    accepted = bool(is_valid and _accepted_proof(task_dict))
    if not accepted:
        verdict = "FAIL"
        is_valid = False
    else:
        verdict = "PASS"

    if accepted and integrity_status == STATUS_VERIFIED_MATCH:
        human_summary = f"Artifact '{name}' ({size_fmt}) verified authentic (SHA-256: {fingerprint})."
    elif accepted and integrity_status == STATUS_EXTERNAL_PRODUCED:
        human_summary = f"Artifact '{name}' ({size_fmt}) received from external build (SHA-256: {fingerprint})."
    elif claimed == "FAIL":
        human_summary = f"WARNING: Artifact '{name}' was not accepted (verification verdict FAIL)."
    elif integrity_status == STATUS_HASH_MISMATCH:
        human_summary = f"WARNING: Artifact '{name}' failed integrity check (hash mismatch against expected digest)."
    elif resolution != "verified":
        human_summary = f"WARNING: Artifact '{name}' has no verified resolution."
    else:
        human_summary = f"WARNING: Artifact '{name}' record is missing or corrupt."

    return {
        "artifact_id": artifact_id,
        "name": name,
        "size_bytes": size,
        "size_formatted": size_fmt,
        "sha256": sha256_hex,
        "sha256_fingerprint": fingerprint,
        "integrity_status": integrity_status,
        "is_valid": is_valid,
        "verification_verdict": verdict,
        "provenance": {
            "task_id": record.get("task_id") or task_dict.get("task_id"),
            "goal_id": record.get("goal_id") or task_dict.get("goal_id"),
            "worker_id": record.get("worker_id"),
            "dispatch_id": record.get("dispatch_id"),
            "attempt_id": record.get("attempt_id"),
            "branch": record.get("branch") or task_dict.get("branch"),
            "source_sha": record.get("source_sha") or task_dict.get("source_sha"),
        },
        "human_summary": human_summary,
        "file_access": {
            "download_url": f"{download_base_url}/{artifact_id}",
            "local_path": local_path,
        },
    }


def verify_artifact_receipt(
    receipt: Mapping[str, Any],
    data: bytes,
    *,
    expected_branch: str | None = None,
    expected_source_sha: str | None = None,
) -> tuple[bool, str]:
    """Verify in-memory or downloaded bytes against a receipt.

    Matching bytes are not acceptance. The receipt itself must say PASS,
    is_valid, and an accepted integrity status.
    """
    if receipt.get("verification_verdict") != "PASS":
        return False, "verdict not accepted"
    if receipt.get("is_valid") is not True:
        return False, "receipt not valid"
    if receipt.get("integrity_status") not in (STATUS_VERIFIED_MATCH, STATUS_EXTERNAL_PRODUCED):
        return False, "integrity not accepted"
    actual_sha = hashlib.sha256(data).hexdigest()
    if actual_sha != receipt.get("sha256"):
        return False, f"hash mismatch: expected {receipt.get('sha256')}, got {actual_sha}"

    expected_size = receipt.get("size_bytes")
    if expected_size is not None and len(data) != expected_size:
        return False, f"size mismatch: expected {expected_size} bytes, got {len(data)}"

    prov = receipt.get("provenance") or {}
    if expected_branch is not None and prov.get("branch") != expected_branch:
        return False, f"branch mismatch: expected {expected_branch}, got {prov.get('branch')}"

    if expected_source_sha is not None and prov.get("source_sha") != expected_source_sha:
        return False, f"source_sha mismatch: expected {expected_source_sha}, got {prov.get('source_sha')}"

    return True, "VERIFIED"
