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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--processed-dir", required=True)
    args = parser.parse_args()

    task_path = Path(args.task)
    processed_dir = Path(args.processed_dir)
    task = json.loads(task_path.read_text(encoding="utf-8"))
    if set(task) != REQUIRED:
        fail("unexpected envelope fields")
    if task["schema_version"] != "2.0":
        fail("unsupported schema_version")
    if task["type"] != "TASK" or task["status"] != "NEW":
        fail("message is not a new TASK")
    if task["source"] != "github_courier" or task["destination"] != "codex":
        fail("unexpected route")
    if not all(isinstance(task[key], str) and task[key] for key in ("message_id", "task_id", "correlation_id", "payload_hash")):
        fail("missing identity field")
    if task["parent_id"] is not None:
        fail("TASK parent_id must be null")
    if task["max_iterations"] != 1:
        fail("max_iterations must be exactly 1")
    if not isinstance(task["payload"], dict) or canonical_hash(task["payload"]) != task["payload_hash"]:
        fail("payload_hash mismatch")
    if task["payload"].get("result_request") not in {"COURIER_CODEX_ACK", "COURIER_SEQUENTIAL_ACK", "COURIER_AUTOMATIC_ACK"}:
        fail("unsupported result_request")

    for candidate in processed_dir.glob("*.json"):
        try:
            processed = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if processed.get("parent_id") == task["message_id"] or processed.get("message_id") == task["message_id"]:
            fail("TASK already has a terminal record")

    print(task_path.as_posix())


if __name__ == "__main__":
    main()
