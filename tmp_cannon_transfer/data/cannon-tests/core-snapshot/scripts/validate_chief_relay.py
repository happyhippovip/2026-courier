#!/usr/bin/env python3
"""Deterministic validation for Antigravity Result and Chief Command events."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
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


def check_dedupe(candidate_path: Path, candidate_message_id: str, search_dirs: list[Path]) -> None:
    candidate_real = candidate_path.resolve()
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for existing_file in search_dir.glob("*.json"):
            if existing_file.resolve() == candidate_real:
                continue
            try:
                existing_data = json.loads(existing_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            if existing_data.get("message_id") == candidate_message_id:
                fail(f"duplicate message_id '{candidate_message_id}' already exists in {existing_file.as_posix()}")


def validate_event(file_path: Path, processed_dir: Path | None = None, incoming_dir: Path | None = None) -> dict:
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

    if not isinstance(data.get("message_id"), str) or not data["message_id"]:
        fail("message_id must be a non-empty string")

    # Enforce deduplication against search directories if provided
    search_dirs = [d for d in [processed_dir, incoming_dir] if d is not None]
    if search_dirs:
        check_dedupe(file_path, data["message_id"], search_dirs)

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
    parser.add_argument("--processed-dir", required=False, default=None, help="Directory with processed events")
    parser.add_argument("--incoming-dir", required=False, default=None, help="Directory with incoming events")
    args = parser.parse_args()

    processed_dir = Path(args.processed_dir) if args.processed_dir else None
    incoming_dir = Path(args.incoming_dir) if args.incoming_dir else None

    data = validate_event(Path(args.file), processed_dir=processed_dir, incoming_dir=incoming_dir)
    print(f"VALIDATION_PASS: type={data['type']}, id={data['message_id']}, task={data['task_id']}")


if __name__ == "__main__":
    main()
