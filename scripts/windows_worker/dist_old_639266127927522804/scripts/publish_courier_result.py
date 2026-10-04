#!/usr/bin/env python3
"""Publish only a schema-valid Codex RESULT for one validated courier TASK."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


EXPECTED = {
    "schema_version", "message_id", "task_id", "correlation_id", "parent_id",
    "source", "destination", "type", "status", "created_at", "payload",
    "payload_hash", "max_iterations",
}


def fail(message: str) -> None:
    raise SystemExit(f"invalid Codex courier result: {message}")


def payload_hash(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--processed-dir", required=True)
    parser.add_argument("--github-output", required=True)
    args = parser.parse_args()

    task = json.loads(Path(args.task).read_text(encoding="utf-8"))
    raw_result = os.environ.get("CODEX_RESULT_JSON", "")
    try:
        result = json.loads(raw_result)
    except json.JSONDecodeError as exc:
        fail(f"Codex output is not JSON: {exc.msg}")

    if set(result) != EXPECTED:
        fail("unexpected envelope fields")
    if result["schema_version"] != "2.0" or result["type"] != "RESULT" or result["status"] != "DONE":
        fail("unexpected result lifecycle")
    if result["source"] != "codex" or result["destination"] != "github_courier":
        fail("unexpected route")
    if result["task_id"] != task["task_id"] or result["correlation_id"] != task["correlation_id"]:
        fail("task or correlation mismatch")
    if result["parent_id"] != task["message_id"] or result["message_id"] == task["message_id"]:
        fail("parent or message identity mismatch")
    if result["max_iterations"] != task["max_iterations"] or result["max_iterations"] != 1:
        fail("iteration bound mismatch")
    expected_result = task.get("payload", {}).get("result_request")
    if expected_result not in {"COURIER_CODEX_ACK", "COURIER_SEQUENTIAL_ACK", "COURIER_AUTOMATIC_ACK"}:
        fail("unsupported task result_request")
    if result["payload"] != {"result": expected_result}:
        fail("unexpected payload")
    if result["payload_hash"] != payload_hash(result["payload"]):
        fail("payload hash mismatch")
    if not result["message_id"].replace("-", "").replace("_", "").replace(".", "").isalnum():
        fail("unsafe result message_id")

    processed_dir = Path(args.processed_dir)
    for candidate in processed_dir.glob("*.json"):
        try:
            existing = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if existing.get("parent_id") == task["message_id"] or existing.get("message_id") == result["message_id"]:
            fail("duplicate terminal result")

    target = processed_dir / f"{task['message_id']}.result.json"
    if target.exists():
        fail("terminal result path already exists")
    target.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    with Path(args.github_output).open("a", encoding="utf-8") as output:
        output.write(f"result_path={target.as_posix()}\n")


if __name__ == "__main__":
    main()
