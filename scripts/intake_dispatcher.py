#!/usr/bin/env python3
"""Intake Dispatcher.

Admits customer revenue intake requests and dispatches them to the qualified execution pipeline,
atomically updating the central state.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid


def dispatch_intake(intake_file, repo_dir=None, state_file=None, dry_run=False):
    with open(intake_file, "r", encoding="utf-8") as f:
        intake = json.load(f)

    required_fields = ["target_owner", "target_repo", "target_sha", "customer_reference"]
    missing = [field for field in required_fields if not intake.get(field)]
    if missing:
        raise ValueError(f"Intake missing required fields: {', '.join(missing)}")

    task_id = f"task-revenue-{uuid.uuid4().hex[:8]}"
    print(f"Admitting intake {intake.get('customer_reference')} as {task_id}")

    execution_ref = "DISPATCHED_DRY_RUN"
    if not dry_run:
        gh_bin = shutil.which("gh") or shutil.which("gh.exe") or "gh"
        cmd = [
            gh_bin, "workflow", "run", "revenue_v1_baseline.yml",
            "-f", f"target_owner={intake['target_owner']}",
            "-f", f"target_repo={intake['target_repo']}",
            "-f", f"target_sha={intake['target_sha']}",
            "-f", f"customer_reference={intake['customer_reference']}",
            "-f", f"price_currency={intake.get('price_currency', 'EUR_99')}",
            "-f", f"delivery_destination={intake.get('delivery_destination', 'none')}",
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            print("Successfully dispatched to GitHub Actions worker.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to dispatch: {e.stderr}")
            raise

        time.sleep(3)
        run_info = subprocess.run(
            [gh_bin, "run", "list", "--workflow=revenue_v1_baseline.yml", "--limit=1", "--json", "databaseId", "-q", ".[0].databaseId"],
            capture_output=True, text=True,
        )
        found_ref = run_info.stdout.strip()
        if found_ref:
            execution_ref = found_ref

    # Update Central State
    if repo_dir is None:
        repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if state_file is None:
        state_file = os.path.join(repo_dir, "central_state.json")

    try:
        if os.path.exists(state_file):
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
        else:
            state = {"tasks": {}}
    except Exception:
        state = {"tasks": {}}

    state.setdefault("tasks", {})[task_id] = {
        "task_id": task_id,
        "customer_reference": intake["customer_reference"],
        "worker_id": "github-actions-revenue-v1",
        "platform": "github",
        "dispatch_ref": "intake_dispatcher_local",
        "execution_ref": execution_ref,
        "state": "DISPATCHED_TO_EXTERNAL",
        "last_transition": "AUTOMATIC_DISPATCH",
        "next_explicit_transition": "WAIT_FOR_GITHUB_PR",
        "real_wall": "HUMAN_REVIEW_REQUIRED_ON_PR",
    }

    dir_name = os.path.dirname(state_file) or "."
    fd, tmp_file = tempfile.mkstemp(dir=dir_name, prefix="state_", suffix=".tmp")
    with open(fd, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp_file, state_file)

    print("Central state updated. System chain fully connected for intake -> execution -> PR.")
    return {
        "task_id": task_id,
        "execution_ref": execution_ref,
        "status": "DISPATCHED",
    }


def main():
    parser = argparse.ArgumentParser(description="Courier Intake Dispatcher")
    parser.add_argument("intake_file", help="Path to intake JSON file")
    parser.add_argument("--repo-dir", help="Path to repository root")
    parser.add_argument("--state-file", help="Path to central state file")
    parser.add_argument("--dry-run", action="store_true", help="Simulate dispatch without GitHub call")
    parser.add_argument("--json", action="store_true", help="Output result as JSON")
    args = parser.parse_args()

    res = dispatch_intake(
        args.intake_file,
        repo_dir=args.repo_dir,
        state_file=args.state_file,
        dry_run=args.dry_run,
    )
    if args.json:
        print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
