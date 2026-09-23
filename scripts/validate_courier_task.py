#!/usr/bin/env python3
"""Deterministic validation for a trusted v2 courier TASK.

This script makes no network calls and never executes a payload. It is used by
the disabled GitHub Actions preparation to reject malformed, replayed, or
non-TASK envelopes before Codex can be invoked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


REQUIRED = {
    "schema_version", "message_id", "task_id", "correlation_id", "parent_id",
    "source", "destination", "type", "status", "created_at", "payload",
    "payload_hash", "max_iterations",
}


def fail(message: str) -> None:
    raise SystemExit(f"invalid courier task: {message}")


def canonical_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def validate_task(task_path: Path | str, processed_dir: Path | str) -> dict:
    t_path = Path(task_path)
    p_dir = Path(processed_dir)
    if not t_path.exists():
        fail(f"task file does not exist: {t_path}")
    try:
        task = json.loads(t_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"malformed task json: {exc}")

    if set(task) != REQUIRED:
        fail("unexpected envelope fields")
    if task.get("schema_version") != "2.0":
        fail("unsupported schema_version")
    if task.get("type") != "TASK" or task.get("status") != "NEW":
        fail("message is not a new TASK")
    if task.get("source") != "github_courier" or task.get("destination") != "codex":
        fail("unexpected route")
    if not all(isinstance(task.get(key), str) and task.get(key) for key in ("message_id", "task_id", "correlation_id", "payload_hash")):
        fail("missing identity field")
    if task.get("parent_id") is not None:
        fail("TASK parent_id must be null")
    if task.get("max_iterations") != 1:
        fail("max_iterations must be exactly 1")
    if not isinstance(task.get("payload"), dict) or canonical_hash(task["payload"]) != task.get("payload_hash"):
        fail("payload_hash mismatch")
    if task.get("payload", {}).get("result_request") not in {"COURIER_CODEX_ACK", "COURIER_SEQUENTIAL_ACK", "COURIER_AUTOMATIC_ACK"}:
        fail("unsupported result_request")

    if p_dir.exists():
        for candidate in p_dir.glob("*.json"):
            try:
                processed = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if processed.get("parent_id") == task["message_id"] or processed.get("message_id") == task["message_id"]:
                fail("TASK already has a terminal record")

    return task


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--processed-dir", required=True)
    args = parser.parse_args()

    task_path = Path(args.task)
    validate_task(task_path, args.processed_dir)
    print(task_path.as_posix())


if __name__ == "__main__":
    main()
