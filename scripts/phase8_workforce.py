#!/usr/bin/env python3
"""Bounded, deterministic Phase 8 workforce canary; never executes task input."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


CAPABILITY = "repository-policy-digest-v1"
SCOPE = ".github/github-actions-policy.json"
RESULT_CONTRACT = "sha256-of-scope-v1"
VERIFIER_ID = "phase8-independent-verifier-v1"
IDENTITY = ("goal_id", "task_id", "attempt_id", "idempotency_key")
SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def fail(message: str) -> None:
    raise SystemExit(f"phase8 workforce rejected: {message}")


def load(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read {path}: {exc}")
    if not isinstance(value, dict):
        fail(f"{path} must contain an object")
    return value


def digest(path: Path, max_bytes: int) -> str:
    data = path.read_bytes()
    if len(data) > max_bytes:
        fail("scope exceeds task budget")
    return hashlib.sha256(data).hexdigest()


def validate_task(task: dict[str, object]) -> None:
    required = {"schema_version", *IDENTITY, "capability", "scope", "budget", "result_contract", "proposal_mode"}
    if set(task) != required:
        fail("unexpected task fields")
    if task["schema_version"] != "1.0":
        fail("unsupported schema version")
    if any(not isinstance(task[key], str) or not SAFE_ID.fullmatch(task[key]) for key in IDENTITY):
        fail("invalid task identity")
    if len({task[key] for key in IDENTITY}) != len(IDENTITY):
        fail("task identities must be distinct")
    if task["capability"] != CAPABILITY or task["scope"] != SCOPE or task["result_contract"] != RESULT_CONTRACT:
        fail("capability, scope, or result contract is not allowed")
    if task["proposal_mode"] != "PR_ONLY":
        fail("results may only be proposed through a pull request")
    budget = task["budget"]
    if not isinstance(budget, dict) or set(budget) != {"max_files", "max_bytes"}:
        fail("invalid budget")
    if budget.get("max_files") != 1 or not isinstance(budget.get("max_bytes"), int) or not 0 < budget["max_bytes"] <= 65536:
        fail("budget exceeds capability limit")


def worker(task: dict[str, object], root: Path, run_id: str, run_attempt: str) -> dict[str, object]:
    validate_task(task)
    if not run_id.isdecimal() or not run_attempt.isdecimal():
        fail("invalid GitHub run identity")
    return {
        "schema_version": "1.0", **{key: task[key] for key in IDENTITY},
        "capability": CAPABILITY, "scope": SCOPE, "budget": task["budget"],
        "result_contract": RESULT_CONTRACT, "github_run_id": run_id,
        "github_run_attempt": run_attempt, "worker_result_id": f"worker-{task['attempt_id']}",
        "worker_status": "PASS", "proposal_mode": "PR_ONLY",
        "digest_sha256": digest(root / SCOPE, task["budget"]["max_bytes"]),
    }


def verify(task: dict[str, object], candidate: dict[str, object], root: Path, existing_dir: Path, run_id: str, run_attempt: str) -> dict[str, object]:
    validate_task(task)
    expected = worker(task, root, run_id, run_attempt)
    if set(candidate) != set(expected) or candidate != expected:
        fail("worker result does not independently satisfy the task contract")
    existing_dir.mkdir(parents=True, exist_ok=True)
    for path in existing_dir.glob("*.json"):
        prior = load(path)
        if prior.get("idempotency_key") == task["idempotency_key"]:
            fail("idempotency key already has a durable result")
    return {**candidate, "verifier_id": VERIFIER_ID, "verifier_status": "PASS"}


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "worker", "verify"):
        sub = commands.add_parser(name)
        sub.add_argument("--task", type=Path, required=True)
    worker_parser = commands.choices["worker"]
    worker_parser.add_argument("--root", type=Path, default=Path("."))
    worker_parser.add_argument("--run-id", required=True)
    worker_parser.add_argument("--run-attempt", required=True)
    verify_parser = commands.choices["verify"]
    verify_parser.add_argument("--candidate", type=Path, required=True)
    verify_parser.add_argument("--root", type=Path, default=Path("."))
    verify_parser.add_argument("--existing-dir", type=Path, required=True)
    verify_parser.add_argument("--output", type=Path, required=True)
    verify_parser.add_argument("--run-id", required=True)
    verify_parser.add_argument("--run-attempt", required=True)
    args = parser.parse_args()
    task = load(args.task)
    if args.command == "validate":
        validate_task(task)
        return
    if args.command == "worker":
        print(json.dumps(worker(task, args.root, args.run_id, args.run_attempt), sort_keys=True))
        return
    result = verify(task, load(args.candidate), args.root, args.existing_dir, args.run_id, args.run_attempt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
