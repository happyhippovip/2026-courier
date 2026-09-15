#!/usr/bin/env python3
"""Thin, deterministic operator entrypoint for the accepted Revenue V1 lane."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

LANE = "github-actions-revenue-v1"
WORKFLOW = "revenue_v1_baseline.yml"
TASK_PATTERN = re.compile(r"^task-[a-z0-9-]+$")


def fail(message: str) -> None:
    raise SystemExit(f"operator automation rejected: {message}")


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read durable JSON {path}: {error}")
    if not isinstance(value, dict):
        fail(f"durable JSON {path} is not an object")
    return value


def run(command: list[str], *, capture: bool = False) -> str:
    completed = subprocess.run(command, check=True, text=True, capture_output=capture)
    return completed.stdout.strip() if capture else ""


def commit_paths(root: Path, paths: list[Path], message: str, no_git: bool) -> str | None:
    if no_git:
        return None
    run(["git", "-C", str(root), "add", *[str(path.relative_to(root)) for path in paths]])
    changed = subprocess.run(
        ["git", "-C", str(root), "diff", "--cached", "--quiet"], text=True
    ).returncode == 1
    if changed:
        run([
            "git", "-C", str(root), "commit", "-m", message,
            "-m", "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>",
        ])
        run(["git", "-C", str(root), "push", "origin", "HEAD"])
    return run(["git", "-C", str(root), "rev-parse", "HEAD"], capture=True)


def packet_for(args: argparse.Namespace) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.target_owner):
        fail("target_owner is invalid")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", args.target_repo):
        fail("target_repo is invalid")
    if not re.fullmatch(r"[0-9a-fA-F]{40}", args.target_sha):
        fail("target_sha must be an immutable 40-character SHA")
    if not re.fullmatch(r"EUR [0-9]+\.[0-9]{2}", args.price_currency):
        fail("price_currency must use the bounded EUR 0.00 format")
    if not args.customer_reference or not args.delivery_destination:
        fail("customer_reference and delivery_destination are required")
    intent = "|".join([
        args.goal_id, args.target_owner, args.target_repo, args.target_sha.lower(),
        args.customer_reference, args.price_currency, args.delivery_destination,
    ])
    digest = hashlib.sha256(intent.encode("utf-8")).hexdigest()[:16]
    return {
        "schema_version": "1.0",
        "goal_id": args.goal_id,
        "task_id": f"task-{digest}",
        "attempt_id": "attempt-001",
        "idempotency_key": f"rev-v1-{digest}",
        "capability": "github-actions-safety-baseline-v1",
        "execution_lane": LANE,
        "scope": "public-repo-inspection",
        "target_owner": args.target_owner,
        "target_repo": args.target_repo,
        "target_sha": args.target_sha.lower(),
        "customer_reference": args.customer_reference,
        "price_currency": args.price_currency,
        "delivery_destination": args.delivery_destination,
        "budget": {"max_files": 100, "max_bytes": 1048576},
        "result_contract": "revenue-v1-report",
        "proposal_mode": "PR_ONLY",
        "cost_tracking": {"compute_cost": None},
        "human_minutes": 0,
    }


def validate_public_target(packet: dict[str, Any]) -> None:
    repository = f"{packet['target_owner']}/{packet['target_repo']}"
    details = json.loads(run(["gh", "api", f"repos/{repository}"], capture=True))
    if details.get("private") is not False:
        fail("Revenue V1 accepts only a publicly readable target repository")
    resolved_sha = run(
        ["gh", "api", f"repos/{repository}/commits/{packet['target_sha']}", "--jq", ".sha"],
        capture=True,
    ).lower()
    if resolved_sha != packet["target_sha"]:
        fail("target_sha is not a readable immutable commit in the public target")


def initial_state(packet: dict[str, Any], task_path: Path) -> dict[str, Any]:
    return {
        "goal_id": packet["goal_id"],
        "task_id": packet["task_id"],
        "attempt_id": packet["attempt_id"],
        "state": "PRE_DISPATCH_ADMITTED",
        "owner": "operator",
        "platform": "github-actions",
        "last_transition": "PRE_DISPATCH_ADMISSION",
        "durable_ref": str(task_path),
        "next_explicit_transition": "DISPATCH_REVENUE_V1",
        "real_wall": None,
        "cost_or_quota_if_known": packet["cost_tracking"]["compute_cost"],
        "revenue_if_known": packet["price_currency"],
    }


def reconcile(state: dict[str, Any], reconciliation: dict[str, Any], result_path: str) -> dict[str, Any]:
    required = ("task_id", "attempt_id", "proposal_pr", "proposal_head")
    if reconciliation.get("status") != "HANDOFF_RECONCILED" or any(not reconciliation.get(key) for key in required):
        fail("DurableResult reconciliation is not an admitted handoff")
    if reconciliation["task_id"] != state["task_id"] or reconciliation["attempt_id"] != state["attempt_id"]:
        fail("DurableResult does not belong to the active TaskPacket")
    if reconciliation.get("next_safe_state") != "HUMAN_REVIEW_REQUIRED":
        fail("only the explicit HUMAN_REVIEW_REQUIRED transition is permitted")
    return {
        **state,
        "state": "HUMAN_REQUIRED",
        "last_transition": "HANDOFF_RECONCILED",
        "durable_ref": result_path,
        "next_explicit_transition": "HUMAN_REVIEW_REQUIRED",
        "real_wall": "HUMAN_REVIEW_REQUIRED: review the proposal before customer delivery or payment action",
    }


def start(args: argparse.Namespace) -> None:
    root = args.root.resolve()
    packet = packet_for(args)
    if not args.dry_run:
        validate_public_target(packet)
    task_path = root / "revenue_v1" / "taskpackets" / f"{packet['task_id']}.json"
    state_path = root / "revenue_v1" / "operator_state.json"
    if state_path.exists():
        existing = read_json(state_path)
        if existing.get("task_id") == packet["task_id"]:
            print(json.dumps(existing, sort_keys=True))
            return
        if existing.get("state") not in {"HUMAN_REQUIRED"}:
            fail("another admitted task owns the single operator state")
    write_json(task_path, packet)
    state = initial_state(packet, task_path.relative_to(root))
    write_json(state_path, state)
    courier_ref = commit_paths(root, [task_path, state_path], f"Revenue V1: admit {packet['task_id']}", args.no_git)
    if courier_ref:
        state["durable_ref"] = f"{task_path.relative_to(root)}@{courier_ref}"
        write_json(state_path, state)
        commit_paths(root, [state_path], f"Revenue V1: record admitted {packet['task_id']}", args.no_git)
    if args.dry_run:
        print(json.dumps(state, sort_keys=True))
        return
    if not courier_ref:
        fail("Git persistence is required before dispatch")
    branch = run(["git", "-C", str(root), "branch", "--show-current"], capture=True)
    run([
        "gh", "workflow", "run", WORKFLOW, "--repo", args.repository, "--ref", branch,
        "-f", f"courier_ref={courier_ref}",
        "-f", f"task_packet_path={task_path.relative_to(root)}",
    ])
    state.update({
        "state": "EXECUTION_DISPATCHED",
        "last_transition": "EXECUTE_REVENUE_V1",
        "next_explicit_transition": "CONSUME_DURABLE_RESULT",
    })
    write_json(state_path, state)
    commit_paths(root, [state_path], f"Revenue V1: dispatch {packet['task_id']}", args.no_git)
    if args.no_wait:
        print(json.dumps(state, sort_keys=True))
        return
    run_id = run([
        "gh", "run", "list", "--repo", args.repository, "--workflow", WORKFLOW,
        "--branch", branch, "--limit", "1", "--json", "databaseId",
        "--jq", ".[0].databaseId",
    ], capture=True)
    if not run_id.isdecimal():
        fail("GitHub did not return a workflow run identity")
    watch = subprocess.run(["gh", "run", "watch", run_id, "--repo", args.repository, "--exit-status"])
    if watch.returncode != 0:
        state.update({
            "state": "REAL_WALL",
            "last_transition": "EXECUTION_FAILED",
            "next_explicit_transition": "HUMAN_REQUIRED",
            "real_wall": f"GitHub Actions run {run_id} failed; inspect the durable run before retrying",
        })
        write_json(state_path, state)
        commit_paths(root, [state_path], f"Revenue V1: record failed {packet['task_id']}", args.no_git)
        fail(f"GitHub Actions run {run_id} failed and was recorded as a real wall")
    with tempfile.TemporaryDirectory(prefix="revenue-v1-artifacts-") as temporary:
        artifact_root = Path(temporary)
        run([
            "gh", "run", "download", run_id, "--repo", args.repository,
            "--name", "handoff-artifacts", "--dir", str(artifact_root),
        ])
        reconciliation_path = artifact_root / "reconciliation.json"
        if not reconciliation_path.exists():
            fail("workflow completed without a reconciliation artifact")
        state = reconcile(
            state,
            read_json(reconciliation_path),
            f"workflow-run:{run_id}/handoff-artifacts/reconciliation.json",
        )
    write_json(state_path, state)
    commit_paths(root, [state_path], f"Revenue V1: reconcile {packet['task_id']}", args.no_git)
    print(json.dumps(state, sort_keys=True))


def apply_reconciliation(args: argparse.Namespace) -> None:
    state_path = args.root.resolve() / "revenue_v1" / "operator_state.json"
    state = reconcile(read_json(state_path), read_json(args.reconciliation), args.result_ref)
    write_json(state_path, state)
    commit_paths(args.root.resolve(), [state_path], f"Revenue V1: reconcile {state['task_id']}", args.no_git)
    print(json.dumps(state, sort_keys=True))


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--root", type=Path, default=Path("."))
    command.add_argument("--repository", default="happyhippovip/2026-courier")
    command.add_argument("--no-git", action="store_true")
    subcommands = command.add_subparsers(dest="command", required=True)
    start_parser = subcommands.add_parser("start")
    start_parser.add_argument("--goal-id", default="rev-v1-customer-job")
    start_parser.add_argument("--target-owner", required=True)
    start_parser.add_argument("--target-repo", required=True)
    start_parser.add_argument("--target-sha", required=True)
    start_parser.add_argument("--customer-reference", required=True)
    start_parser.add_argument("--price-currency", default="EUR 99.00")
    start_parser.add_argument("--delivery-destination", required=True)
    start_parser.add_argument("--dry-run", action="store_true")
    start_parser.add_argument("--no-wait", action="store_true")
    subcommands.add_parser("reconcile").add_argument("--reconciliation", type=Path, required=True)
    subcommands.choices["reconcile"].add_argument("--result-ref", required=True)
    return command


if __name__ == "__main__":
    arguments = parser().parse_args()
    if arguments.command == "start":
        start(arguments)
    else:
        apply_reconciliation(arguments)
