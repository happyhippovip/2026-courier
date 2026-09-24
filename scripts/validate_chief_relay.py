#!/usr/bin/env python3
"""Deterministic validation for Antigravity Result and Chief Command events."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

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


class RelayValidationError(ValueError):
    """Raised when a Chief Relay event fails validation."""


def fail(message: str) -> None:
    raise RelayValidationError(f"VALIDATION_ERROR: {message}")


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


def validate_event(file_path: Path, processed_dir: Path | None = None, incoming_dir: Path | None = None) -> dict[str, Any]:
    if not file_path.exists():
        fail(f"File does not exist: {file_path}")
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"Invalid JSON in {file_path}: {exc}")

    if not isinstance(data, dict):
        fail("Event must be a JSON object")

    if set(data) != REQUIRED_ENVELOPE:
        fail(f"Envelope fields mismatch: got {set(data)}, expected {REQUIRED_ENVELOPE}")

    if data.get("schema_version") != "2.0":
        fail(f"Unsupported schema_version: {data.get('schema_version')}")

    if data.get("max_iterations") != 1:
        fail(f"max_iterations must be 1, got {data.get('max_iterations')}")

    if not isinstance(data.get("message_id"), str) or not data["message_id"]:
        fail("message_id must be a non-empty string")

    # Enforce deduplication against search directories if provided
    search_dirs = [d for d in [processed_dir, incoming_dir] if d is not None]
    if search_dirs:
        check_dedupe(file_path, data["message_id"], search_dirs)

    if canonical_hash(data.get("payload")) != data.get("payload_hash"):
        fail("payload_hash mismatch")

    event_type = data.get("type")
    payload = data.get("payload")

    if event_type == "RESULT":
        if data.get("source") != "antigravity" or data.get("destination") != "chief":
            fail(f"Invalid route for RESULT: {data.get('source')} -> {data.get('destination')}")
        if data.get("status") not in {"DONE", "FAILED", "BLOCKED"}:
            fail(f"Invalid status for RESULT: {data.get('status')}")
        if not isinstance(payload, dict) or set(payload) != REQUIRED_RESULT_PAYLOAD:
            fail(f"Result payload fields mismatch: got {set(payload) if isinstance(payload, dict) else type(payload)}, expected {REQUIRED_RESULT_PAYLOAD}")
        if payload.get("source_agent") != "ANTIGRAVITY":
            fail(f"source_agent must be ANTIGRAVITY, got {payload.get('source_agent')}")

    elif event_type == "COMMAND":
        if data.get("source") != "chief" or data.get("destination") != "antigravity":
            fail(f"Invalid route for COMMAND: {data.get('source')} -> {data.get('destination')}")
        if data.get("status") != "NEW":
            fail(f"Invalid status for COMMAND: {data.get('status')}")
        if not isinstance(payload, dict) or set(payload) != REQUIRED_COMMAND_PAYLOAD:
            fail(f"Command payload fields mismatch: got {set(payload) if isinstance(payload, dict) else type(payload)}, expected {REQUIRED_COMMAND_PAYLOAD}")
        if payload.get("target_agent") != "ANTIGRAVITY":
            fail(f"target_agent must be ANTIGRAVITY, got {payload.get('target_agent')}")
    else:
        fail(f"Unsupported event type: {event_type}")

    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Chief Relay events")
    parser.add_argument("--file", required=True, help="Path to event JSON")
    parser.add_argument("--processed-dir", required=False, default=None, help="Directory with processed events")
    parser.add_argument("--incoming-dir", required=False, default=None, help="Directory with incoming events")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON status")
    args = parser.parse_args(argv)

    processed_dir = Path(args.processed_dir) if args.processed_dir else None
    incoming_dir = Path(args.incoming_dir) if args.incoming_dir else None

    try:
        data = validate_event(Path(args.file), processed_dir=processed_dir, incoming_dir=incoming_dir)
        if args.json:
            print(json.dumps({"valid": True, "event": data}, indent=2))
        else:
            print(f"VALIDATION_PASS: type={data['type']}, id={data['message_id']}, task={data['task_id']}")
        return 0
    except RelayValidationError as exc:
        if args.json:
            print(json.dumps({"valid": False, "error": str(exc)}, indent=2))
        else:
            print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
