#!/usr/bin/env python3
"""Deterministic validation for Antigravity Result and Chief Command events."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


REQUIRED_ENVELOPE = {
    "schema_version", "message_id", "task_id", "correlation_id", "parent_id",
    "source", "destination", "type", "status", "created_at", "payload",
    "payload_hash", "max_iterations",
}

REQUIRED_RESULT_PAYLOAD = {
    "source_agent", "summary", "verified_facts", "files_changed",
    "commits", "test_results", "cost", "human_gate", "safe_next_state",
}

REQUIRED_COMMAND_PAYLOAD = {
    "target_agent", "one_next_command", "allowed_scope",
    "human_gate_policy", "cost_policy",
}


def fail(message: str) -> None:
    raise SystemExit(f"VALIDATION_ERROR: {message}")


def canonical_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_event(file_path: Path) -> dict:
    if not file_path.exists():
        fail(f"File does not exist: {file_path}")
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"Invalid JSON in {file_path}: {exc}")

    if set(data) != REQUIRED_ENVELOPE:
        fail(f"Envelope fields mismatch: got {set(data)}, expected {REQUIRED_ENVELOPE}")

    if data["schema_version"] != "2.0":
        fail(f"Unsupported schema_version: {data['schema_version']}")

    if data["max_iterations"] != 1:
        fail(f"max_iterations must be 1, got {data['max_iterations']}")

    if canonical_hash(data["payload"]) != data["payload_hash"]:
        fail("payload_hash mismatch")

    event_type = data["type"]
    payload = data["payload"]

    if event_type == "RESULT":
        if data["source"] != "antigravity" or data["destination"] != "chief":
            fail(f"Invalid route for RESULT: {data['source']} -> {data['destination']}")
        if data["status"] not in {"DONE", "FAILED", "BLOCKED"}:
            fail(f"Invalid status for RESULT: {data['status']}")
        if set(payload) != REQUIRED_RESULT_PAYLOAD:
            fail(f"Result payload fields mismatch: got {set(payload)}, expected {REQUIRED_RESULT_PAYLOAD}")
        if payload["source_agent"] != "ANTIGRAVITY":
            fail(f"source_agent must be ANTIGRAVITY, got {payload['source_agent']}")

    elif event_type == "COMMAND":
        if data["source"] != "chief" or data["destination"] != "antigravity":
            fail(f"Invalid route for COMMAND: {data['source']} -> {data['destination']}")
        if data["status"] != "NEW":
            fail(f"Invalid status for COMMAND: {data['status']}")
        if set(payload) != REQUIRED_COMMAND_PAYLOAD:
            fail(f"Command payload fields mismatch: got {set(payload)}, expected {REQUIRED_COMMAND_PAYLOAD}")
        if payload["target_agent"] != "ANTIGRAVITY":
            fail(f"target_agent must be ANTIGRAVITY, got {payload['target_agent']}")
    else:
        fail(f"Unsupported event type: {event_type}")

    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Chief Relay events")
    parser.add_argument("--file", required=True, help="Path to event JSON")
    args = parser.parse_args()

    data = validate_event(Path(args.file))
    print(f"VALIDATION_PASS: type={data['type']}, id={data['message_id']}, task={data['task_id']}")


if __name__ == "__main__":
    main()
