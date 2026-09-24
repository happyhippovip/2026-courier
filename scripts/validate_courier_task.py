#!/usr/bin/env python3
"""Deterministic validation for a trusted v2 courier TASK.

This script makes no network calls and never executes a payload. It is used by
the GitHub Actions preparation to reject malformed, replayed, or non-TASK
envelopes before Codex can be invoked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REQUIRED = {
    "schema_version", "message_id", "task_id", "correlation_id", "parent_id",
    "source", "destination", "type", "status", "created_at", "payload",
    "payload_hash", "max_iterations",
}

VALID_RESULT_REQUESTS = {
    "COURIER_CODEX_ACK",
    "COURIER_SEQUENTIAL_ACK",
    "COURIER_AUTOMATIC_ACK",
}


class TaskValidationError(ValueError):
    """Raised when a courier task envelope or payload is invalid."""


def canonical_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_task_dict(task: dict[str, Any], processed_dir: Path | None = None) -> tuple[bool, str]:
    if not isinstance(task, dict):
        return False, "TASK must be a JSON object"

    if set(task) != REQUIRED:
        return False, f"unexpected envelope fields: {set(task) ^ REQUIRED}"

    if task.get("schema_version") != "2.0":
        return False, f"unsupported schema_version: {task.get('schema_version')}"

    if task.get("type") != "TASK" or task.get("status") != "NEW":
        return False, f"message is not a new TASK: type={task.get('type')}, status={task.get('status')}"

    if task.get("source") != "github_courier" or task.get("destination") != "codex":
        return False, f"unexpected route: {task.get('source')} -> {task.get('destination')}"

    for key in ("message_id", "task_id", "correlation_id", "payload_hash"):
        val = task.get(key)
        if not isinstance(val, str) or not val:
            return False, f"missing or empty identity field: {key}"

    if task.get("parent_id") is not None:
        return False, "TASK parent_id must be null"

    if task.get("max_iterations") != 1:
        return False, f"max_iterations must be exactly 1, got {task.get('max_iterations')}"

    payload = task.get("payload")
    if not isinstance(payload, dict):
        return False, "payload must be a JSON object"

    if canonical_hash(payload) != task.get("payload_hash"):
        return False, "payload_hash mismatch"

    if payload.get("result_request") not in VALID_RESULT_REQUESTS:
        return False, f"unsupported result_request: {payload.get('result_request')}"

    if processed_dir and processed_dir.exists() and processed_dir.is_dir():
        msg_id = task["message_id"]
        for candidate in processed_dir.glob("*.json"):
            try:
                processed = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if processed.get("parent_id") == msg_id or processed.get("message_id") == msg_id:
                return False, f"TASK already has a terminal record in {candidate.name}"

    return True, "VALID"


def validate_task(task_path: Path | str, processed_dir: Path | str | None = None) -> tuple[bool, str]:
    path = Path(task_path)
    if not path.exists():
        return False, f"Task file not found: {path}"

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"Failed to parse task JSON: {exc}"

    p_dir = Path(processed_dir) if processed_dir else None
    return validate_task_dict(data, processed_dir=p_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Courier Task envelope")
    parser.add_argument("--task", required=True, help="Path to TASK json file")
    parser.add_argument("--processed-dir", help="Directory containing processed/terminal events for deduplication")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    args = parser.parse_args(argv)

    is_valid, reason = validate_task(args.task, args.processed_dir)
    if args.json:
        print(json.dumps({"valid": is_valid, "reason": reason, "task": args.task}, indent=2))
    else:
        if is_valid:
            print(Path(args.task).as_posix())
        else:
            print(f"invalid courier task: {reason}", file=sys.stderr)

    return 0 if is_valid else 1


if __name__ == "__main__":
    sys.exit(main())
