#!/usr/bin/env python3
"""Deterministic Command-to-Worker-Job Builder and Strict JSON Schema Validator for Antigravity with Memory-Aware Context Resolution."""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import uuid
from pathlib import Path

# Import local memory resolver
try:
    from resolve_project_memory import build_memory_context_package, DEFAULT_MEMORY_REPO_PATH
except ImportError:
    from scripts.resolve_project_memory import build_memory_context_package, DEFAULT_MEMORY_REPO_PATH

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

ALLOWED_COST_POLICIES = {"ZERO_COST_ONLY"}
ALLOWED_HUMAN_GATE_POLICIES = {"STOP_ON_HUMAN_GATE_ONLY"}


def fail(message: str) -> None:
    raise SystemExit(f"WORKER_JOB_BUILDER_ERROR: {message}")


def canonical_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_worker_job_against_schema(job_data: dict, schema_path: Path | None = None) -> tuple[bool, str]:
    """Validates worker job data strictly against schemas/antigravity_worker_job.schema.json."""
    if schema_path is None or not schema_path.exists():
        default_schema = Path(__file__).resolve().parent.parent / "schemas/antigravity_worker_job.schema.json"
        if default_schema.exists():
            schema_path = default_schema

    schema = None
    if schema_path and schema_path.exists():
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return False, f"Failed to load schema file {schema_path}: {exc}"

    req_fields = set(schema.get("required", [])) if schema else {
        "schema_version", "job_id", "source_command_message_id", "task_id",
        "correlation_id", "target_agent", "instruction", "allowed_scope",
        "forbidden_scope", "cost_policy", "human_gate_policy", "max_iterations",
        "expected_output", "created_at"
    }

    if not isinstance(job_data, dict):
        return False, "Job data must be a JSON object"

    # All required fields must be present
    if not req_fields.issubset(set(job_data.keys())):
        return False, f"Missing required fields: {req_fields - set(job_data.keys())}"

    # Allowed keys
    allowed_keys = req_fields.union({"memory_context"})
    if not set(job_data.keys()).issubset(allowed_keys):
        return False, f"Unexpected extra fields: {set(job_data.keys()) - allowed_keys}"

    # Property checks
    if job_data.get("schema_version") != "2.0":
        return False, f"Invalid schema_version: {job_data.get('schema_version')} (expected '2.0')"

    if not re.fullmatch(r"job-ag-[A-Za-z0-9_.-]+", str(job_data.get("job_id", ""))):
        return False, f"Invalid job_id pattern: {job_data.get('job_id')}"

    if not re.fullmatch(r"[A-Za-z0-9_.-]+", str(job_data.get("source_command_message_id", ""))):
        return False, f"Invalid source_command_message_id pattern: {job_data.get('source_command_message_id')}"

    if not re.fullmatch(r"[A-Za-z0-9_.-]+", str(job_data.get("task_id", ""))):
        return False, f"Invalid task_id pattern: {job_data.get('task_id')}"

    if not re.fullmatch(r"[A-Za-z0-9_.-]+", str(job_data.get("correlation_id", ""))):
        return False, f"Invalid correlation_id pattern: {job_data.get('correlation_id')}"

    if job_data.get("target_agent") != "ANTIGRAVITY":
        return False, f"Invalid target_agent: {job_data.get('target_agent')} (expected 'ANTIGRAVITY')"

    instruction = job_data.get("instruction")
    if not isinstance(instruction, str) or len(instruction) < 1:
        return False, "instruction must be a non-empty string"

    allowed_scope = job_data.get("allowed_scope")
    if not isinstance(allowed_scope, list) or len(allowed_scope) < 1 or not all(isinstance(x, str) for x in allowed_scope):
        return False, "allowed_scope must be a non-empty list of strings"

    forbidden_scope = job_data.get("forbidden_scope")
    if not isinstance(forbidden_scope, list) or not all(isinstance(x, str) for x in forbidden_scope):
        return False, "forbidden_scope must be a list of strings"

    if job_data.get("cost_policy") != "ZERO_COST_ONLY":
        return False, f"Invalid cost_policy: {job_data.get('cost_policy')} (strictly 'ZERO_COST_ONLY' required)"

    if job_data.get("human_gate_policy") != "STOP_ON_HUMAN_GATE_ONLY":
        return False, f"Invalid human_gate_policy: {job_data.get('human_gate_policy')} (strictly 'STOP_ON_HUMAN_GATE_ONLY' required)"

    if job_data.get("max_iterations") != 1:
        return False, f"Invalid max_iterations: {job_data.get('max_iterations')} (strictly 1 required)"

    if job_data.get("expected_output") != "ANTIGRAVITY_RESULT":
        return False, f"Invalid expected_output: {job_data.get('expected_output')} (strictly 'ANTIGRAVITY_RESULT' required)"

    created_at = job_data.get("created_at")
    if not isinstance(created_at, str) or len(created_at) < 1:
        return False, "created_at must be a non-empty ISO 8601 string"

    # Memory context check if present
    if "memory_context" in job_data:
        m_ctx = job_data["memory_context"]
        if not isinstance(m_ctx, dict):
            return False, "memory_context must be a JSON object"
        m_req = {"memory_repo", "memory_commit", "files_consulted", "relevant_context", "status_labels", "source_references", "generated_at"}
        if set(m_ctx.keys()) != m_req:
            return False, f"memory_context fields mismatch: expected {m_req}, got {set(m_ctx.keys())}"
        if not re.fullmatch(r"[0-9a-fA-F]{7,40}", str(m_ctx.get("memory_commit", ""))):
            return False, f"Invalid memory_commit hash: {m_ctx.get('memory_commit')}"
        if not isinstance(m_ctx.get("files_consulted"), list) or not m_ctx.get("files_consulted"):
            return False, "files_consulted must be a non-empty list of strings"

    return True, "VALID"


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

    # Strict Cost policy check (ZERO_COST_ONLY only)
    if payload.get("cost_policy") not in ALLOWED_COST_POLICIES:
        return False, f"Cost policy violation: '{payload.get('cost_policy')}' is not permitted (strictly {ALLOWED_COST_POLICIES})"

    # Strict Human gate policy check (STOP_ON_HUMAN_GATE_ONLY only)
    if payload.get("human_gate_policy") not in ALLOWED_HUMAN_GATE_POLICIES:
        return False, f"Human gate policy violation: '{payload.get('human_gate_policy')}' is not permitted (strictly {ALLOWED_HUMAN_GATE_POLICIES})"

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


def build_worker_job(
    command_file: Path,
    output_dir: Path,
    schema_path: Path | None = None,
    memory_repo_path: Path | None = None,
) -> dict:
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
    instruction = cmd_data["payload"]["one_next_command"]

    # Resolve read-only memory context package
    mem_repo = memory_repo_path or DEFAULT_MEMORY_REPO_PATH
    memory_context = None
    if mem_repo and mem_repo.exists():
        try:
            memory_context = build_memory_context_package(
                memory_repo_path=mem_repo,
                instruction=instruction,
            )
        except Exception as exc:
            print(f"MEMORY_RESOLVE_WARNING: {exc}", file=sys.stderr)

    worker_job = {
        "schema_version": "2.0",
        "job_id": job_id,
        "source_command_message_id": cmd_data["message_id"],
        "task_id": task_id,
        "correlation_id": cmd_data["correlation_id"],
        "target_agent": "ANTIGRAVITY",
        "instruction": instruction,
        "allowed_scope": list(cmd_data["payload"]["allowed_scope"]),
        "forbidden_scope": list(FORBIDDEN_SCOPES_LIST),
        "cost_policy": cmd_data["payload"]["cost_policy"],
        "human_gate_policy": cmd_data["payload"]["human_gate_policy"],
        "max_iterations": 1,
        "expected_output": "ANTIGRAVITY_RESULT",
        "created_at": created_at,
    }

    if memory_context:
        worker_job["memory_context"] = memory_context

    # Strict JSON Schema validation before emission
    is_schema_valid, schema_err = validate_worker_job_against_schema(worker_job, schema_path)
    if not is_schema_valid:
        fail(f"Generated worker job failed JSON Schema validation: {schema_err}")

    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"{task_id}-worker-job.json"
    out_file.write_text(json.dumps(worker_job, indent=2) + "\n", encoding="utf-8")

    return worker_job


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and Validate Memory-Aware Antigravity Worker Job from Chief Command")
    parser.add_argument("--command", help="Path to Chief command JSON")
    parser.add_argument("--output-dir", default="events/dispatch", help="Output directory for dispatch worker job")
    parser.add_argument("--validate-job", help="Validate an existing worker job file against the JSON Schema")
    parser.add_argument("--schema", help="Custom path to antigravity_worker_job.schema.json")
    parser.add_argument("--memory-repo", default=str(DEFAULT_MEMORY_REPO_PATH), help="Path to 2026-project-memory")
    args = parser.parse_args()

    schema_path = Path(args.schema).resolve() if args.schema else None

    if args.validate_job:
        job_file = Path(args.validate_job)
        if not job_file.exists():
            fail(f"Worker job file not found: {job_file}")
        try:
            job_data = json.loads(job_file.read_text(encoding="utf-8"))
        except Exception as exc:
            fail(f"Invalid JSON in worker job: {exc}")
        valid, msg = validate_worker_job_against_schema(job_data, schema_path)
        if not valid:
            fail(f"Worker job validation failed: {msg}")
        print(f"WORKER_JOB_SCHEMA_VALID: {job_file.name}")
        return

    if not args.command:
        fail("Missing required --command argument")

    command_path = Path(args.command)
    output_dir = Path(args.output_dir)
    mem_repo_path = Path(args.memory_repo).resolve() if args.memory_repo else None

    job = build_worker_job(command_path, output_dir, schema_path, mem_repo_path)
    print(f"WORKER_JOB_CREATED: id={job['job_id']}, task={job['task_id']}, src_msg={job['source_command_message_id']}")


if __name__ == "__main__":
    main()
