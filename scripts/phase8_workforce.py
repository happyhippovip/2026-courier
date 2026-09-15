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


def validate_verified_result(task: dict[str, object], result: dict[str, object], root: Path, run_id: str, run_attempt: str) -> None:
    expected = {
        **worker(task, root, run_id, run_attempt),
        "verifier_id": VERIFIER_ID,
        "verifier_status": "PASS",
    }
    if set(result) != set(expected) or result != expected:
        fail("verifier-approved result does not satisfy the fenced contract")


def reconcile_handoff(
    task: dict[str, object],
    result: dict[str, object],
    handoff: dict[str, object],
    root: Path,
    proposal_number: str,
    proposal_head: str,
    proposal_base: str,
) -> dict[str, object]:
    run_id = result.get("github_run_id")
    run_attempt = result.get("github_run_attempt")
    if not isinstance(run_id, str) or not isinstance(run_attempt, str):
        fail("verified result has no valid GitHub run identity")
    validate_verified_result(task, result, root, run_id, run_attempt)
    if not proposal_number.isdecimal() or proposal_base != "main" or not proposal_head.startswith("phase8/result-proposal-"):
        fail("proposal identity is not a human-reviewable Phase 8 PR")
    expected_handoff = {
        "task_id": result["task_id"],
        "attempt_id": result["attempt_id"],
        "result_path": f"phase8/results/{result['task_id']}-{result['attempt_id']}-{result['github_run_id']}-{result['github_run_attempt']}.json",
        "verifier_id": VERIFIER_ID,
        "result_commit": handoff.get("result_commit"),
        "proposal_branch": proposal_head,
        "proposal_pr": f"https://github.com/happyhippovip/2026-courier/pull/{proposal_number}",
        "human_merge_required": True,
    }
    if not isinstance(expected_handoff["result_commit"], str) or not re.fullmatch(r"[0-9a-f]{40}", expected_handoff["result_commit"]):
        fail("handoff has no valid durable result commit")
    if handoff != expected_handoff:
        fail("handoff does not bind the verified result to the proposal")
    return {
        "status": "HANDOFF_RECONCILED",
        "task_id": result["task_id"],
        "attempt_id": result["attempt_id"],
        "idempotency_key": result["idempotency_key"],
        "github_run_id": result["github_run_id"],
        "github_run_attempt": result["github_run_attempt"],
        "worker_result_id": result["worker_result_id"],
        "verifier_id": VERIFIER_ID,
        "proposal_pr": proposal_number,
        "proposal_head": proposal_head,
        "next_safe_state": "HUMAN_REVIEW_REQUIRED",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "worker", "verify", "validate-result", "reconcile"):
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
    result_parser = commands.choices["validate-result"]
    result_parser.add_argument("--candidate", type=Path, required=True)
    result_parser.add_argument("--root", type=Path, default=Path("."))
    result_parser.add_argument("--run-id", required=True)
    result_parser.add_argument("--run-attempt", required=True)
    reconcile_parser = commands.choices["reconcile"]
    reconcile_parser.add_argument("--result", type=Path, required=True)
    reconcile_parser.add_argument("--handoff", type=Path, required=True)
    reconcile_parser.add_argument("--root", type=Path, default=Path("."))
    reconcile_parser.add_argument("--proposal-number", required=True)
    reconcile_parser.add_argument("--proposal-head", required=True)
    reconcile_parser.add_argument("--proposal-base", required=True)
    reconcile_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    task = load(args.task)
    if args.command == "validate":
        validate_task(task)
        return
    if args.command == "worker":
        print(json.dumps(worker(task, args.root, args.run_id, args.run_attempt), sort_keys=True))
        return
    if args.command == "validate-result":
        validate_verified_result(task, load(args.candidate), args.root, args.run_id, args.run_attempt)
        return
    if args.command == "reconcile":
        reconciliation = reconcile_handoff(
            task, load(args.result), load(args.handoff), args.root,
            args.proposal_number, args.proposal_head, args.proposal_base,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(reconciliation, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return
    result = verify(task, load(args.candidate), args.root, args.existing_dir, args.run_id, args.run_attempt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
