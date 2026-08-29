#!/usr/bin/env python3
"""Deterministic Command-to-Worker-Job Builder and Validator for Antigravity."""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sys
import uuid
from pathlib import Path

REQUIRED_ENVELOPE = {
    "schema_version", "message_id", "task_id", "correlation_id", "parent_id",
    "source", "destination", "type", "status", "created_at", "payload",
    "payload_hash", "max_iterations",
}

REQUIRED_COMMAND_PAYLOAD = {
    "target_agent", "one_next_command", "allowed_scope",
    "human_gate_policy", "cost_policy",
}

ALLOWED_SCOPES_DEFAULT = {
    "happyhippovip/2026-courier",
    "happyhippovip/2026-project-memory",
    "2026-courier",
    "2026-project-memory",
}

FORBIDDEN_SCOPES_LIST = [
    "04-Wellnesskoenig-Website",
    "universuX",
    "FruitKI",
    "2026-Projektzentrale (outside allowed subpaths)",
]

FORBIDDEN_SCOPE_PATTERNS = {
    "04-wellnesskoenig-website",
    "universux",
    "fruitki",
    "2026-projektzentrale",
}

ALLOWED_COST_POLICIES = {"ZERO_COST_ONLY", "FREE_TIER_ONLY"}
ALLOWED_HUMAN_GATE_POLICIES = {"STOP_ON_HUMAN_GATE_ONLY", "AUTO_IF_SAFE"}


def fail(message: str) -> None:
    raise SystemExit(f"WORKER_JOB_BUILDER_ERROR: {message}")


def canonical_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_command_for_job(cmd_data: dict) -> tuple[bool, str]:
    if set(cmd_data) != REQUIRED_ENVELOPE:
        return False, f"Envelope mismatch: {set(cmd_data)} != {REQUIRED_ENVELOPE}"

    if cmd_data.get("schema_version") != "2.0":
        return False, f"Unsupported schema_version: {cmd_data.get('schema_version')}"

    if cmd_data.get("type") != "COMMAND":
        return False, f"Event type must be COMMAND, got {cmd_data.get('type')}"

    if cmd_data.get("status") != "NEW":
        return False, f"Event status must be NEW, got {cmd_data.get('status')}"

    if cmd_data.get("source") != "chief" or cmd_data.get("destination") != "antigravity":
        return False, f"Invalid route: {cmd_data.get('source')} -> {cmd_data.get('destination')}"

    if cmd_data.get("max_iterations") != 1:
        return False, f"max_iterations must be 1, got {cmd_data.get('max_iterations')}"

    payload = cmd_data.get("payload")
    if not isinstance(payload, dict) or set(payload) != REQUIRED_COMMAND_PAYLOAD:
        return False, f"Payload fields mismatch: {set(payload) if isinstance(payload, dict) else type(payload)}"

    if payload.get("target_agent") != "ANTIGRAVITY":
        return False, f"target_agent must be ANTIGRAVITY, got {payload.get('target_agent')}"

    if canonical_hash(payload) != cmd_data.get("payload_hash"):
        return False, "payload_hash mismatch"

    # Cost policy check
    if payload.get("cost_policy") not in ALLOWED_COST_POLICIES:
        return False, f"Cost policy violation: {payload.get('cost_policy')} not in {ALLOWED_COST_POLICIES}"

    # Human gate policy check
    if payload.get("human_gate_policy") not in ALLOWED_HUMAN_GATE_POLICIES:
        return False, f"Human gate policy violation: {payload.get('human_gate_policy')} not in {ALLOWED_HUMAN_GATE_POLICIES}"

    # Scope policy check
    scopes = payload.get("allowed_scope", [])
    if not isinstance(scopes, list) or not scopes:
        return False, "allowed_scope must be a non-empty list"

    for scope in scopes:
        scope_str = str(scope).strip().lower()
        for forbidden in FORBIDDEN_SCOPE_PATTERNS:
            if forbidden in scope_str:
                return False, f"Forbidden scope requested: '{scope}' violates protection of '{forbidden}'"
        if scope not in ALLOWED_SCOPES_DEFAULT:
            return False, f"Scope violation: '{scope}' not in allowed scopes {ALLOWED_SCOPES_DEFAULT}"

    return True, "VALID"


def build_worker_job(command_file: Path, output_dir: Path) -> dict:
    if not command_file.exists():
        fail(f"Command file not found: {command_file}")

    try:
        cmd_data = json.loads(command_file.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"Invalid JSON in command file: {exc}")

    is_valid, reason = validate_command_for_job(cmd_data)
    if not is_valid:
        fail(f"Command validation failed: {reason}")

    task_id = cmd_data["task_id"]
    job_id = f"job-ag-{task_id}-{uuid.uuid4().hex[:8]}"
    created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    worker_job = {
        "schema_version": "2.0",
        "job_id": job_id,
        "source_command_message_id": cmd_data["message_id"],
        "task_id": task_id,
        "correlation_id": cmd_data["correlation_id"],
        "target_agent": "ANTIGRAVITY",
        "instruction": cmd_data["payload"]["one_next_command"],
        "allowed_scope": list(cmd_data["payload"]["allowed_scope"]),
        "forbidden_scope": list(FORBIDDEN_SCOPES_LIST),
        "cost_policy": cmd_data["payload"]["cost_policy"],
        "human_gate_policy": cmd_data["payload"]["human_gate_policy"],
        "max_iterations": 1,
        "expected_output": "ANTIGRAVITY_RESULT",
        "created_at": created_at,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"{task_id}-worker-job.json"
    out_file.write_text(json.dumps(worker_job, indent=2) + "\n", encoding="utf-8")

    return worker_job


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Antigravity Worker Job from Chief Command")
    parser.add_argument("--command", required=True, help="Path to Chief command JSON")
    parser.add_argument("--output-dir", default="events/dispatch", help="Output directory for dispatch worker job")
    args = parser.parse_args()

    command_path = Path(args.command)
    output_dir = Path(args.output_dir)

    job = build_worker_job(command_path, output_dir)
    print(f"WORKER_JOB_CREATED: id={job['job_id']}, task={job['task_id']}, src_msg={job['source_command_message_id']}")


if __name__ == "__main__":
    main()
