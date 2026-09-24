#!/usr/bin/env python3
"""Revenue Customer Intake Submission.

Submits new revenue safety audit goals to the Courier server:
- Seamless credential resolution (env, keyring, .env.txt)
- Full idempotency key binding
- Structured validation and dry-run execution
"""

import argparse
import json
import os
import sys
import uuid
import requests

try:
    from scripts.product_health_check import get_api_key
except ImportError:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from scripts.product_health_check import get_api_key


def submit_intake(owner: str, repo: str, sha: str, customer_ref: str, api_key: str = None, server_url: str = None, repo_dir: str = None, dry_run: bool = False, quiet: bool = False):
    goal_id = f"REVENUE-GOAL-{uuid.uuid4().hex[:8].upper()}"
    task_id = f"REV-{uuid.uuid4().hex[:8].upper()}"

    goal_payload = {
        "goal_id": goal_id,
        "goal_text": f"Revenue Safety Audit for {owner}/{repo}",
        "workflow_plan": [
            {
                "task_id": task_id,
                "type": "revenue_safety_audit",
                "capabilities": ["revenue_safety_audit"],
                "target_owner": owner,
                "target_repo": repo,
                "target_sha": sha,
                "customer_reference": customer_ref,
                "dependencies": [],
                "status": "QUEUED",
                "target_agent": "linux",
                "idempotency_key": task_id,
            }
        ],
    }

    if dry_run:
        if not quiet:
            print(f"[DRY-RUN] Prepared customer intake goal: {goal_id} for {owner}/{repo}")
        return {
            "status": "DRY_RUN",
            "goal_id": goal_id,
            "task_id": task_id,
            "payload": goal_payload,
        }

    key = api_key or get_api_key(repo_dir)
    if not key:
        raise RuntimeError("Missing COURIER_API_KEY, refusing to submit intake.")

    base_url = (server_url or os.environ.get("COURIER_SERVER", "http://127.0.0.1:8080")).rstrip("/")
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    if not quiet:
        print(f"Submitting customer intake goal: {goal_id} for {owner}/{repo}")
    res = requests.post(f"{base_url}/goals", json=goal_payload, headers=headers, timeout=10)
    if res.status_code == 200:
        if not quiet:
            print("Success!")
        return {"status": "SUCCESS", "goal_id": goal_id, "task_id": task_id, "response": res.json()}
    else:
        if not quiet:
            print(f"Failed: {res.status_code} {res.text}")
        return {"status": "FAILED", "status_code": res.status_code, "error": res.text}


def main():
    parser = argparse.ArgumentParser(description="Courier Revenue Customer Intake")
    parser.add_argument("owner", nargs="?", help="Repository owner")
    parser.add_argument("repo", nargs="?", help="Repository name")
    parser.add_argument("sha", nargs="?", help="Target commit SHA")
    parser.add_argument("customer_ref", nargs="?", help="Customer reference ID")
    parser.add_argument("--repo-dir", help="Repository root directory")
    parser.add_argument("--dry-run", action="store_true", help="Simulate intake submission without network call")
    parser.add_argument("--json", action="store_true", help="Output summary as JSON")
    args = parser.parse_args()

    if not args.owner or not args.repo or not args.sha or not args.customer_ref:
        print("Usage: python3 revenue_customer_intake.py <owner> <repo> <sha> <customer_ref> [--dry-run] [--json]")
        sys.exit(1)

    try:
        res = submit_intake(
            owner=args.owner,
            repo=args.repo,
            sha=args.sha,
            customer_ref=args.customer_ref,
            repo_dir=args.repo_dir,
            dry_run=args.dry_run,
            quiet=args.json,
        )
        if args.json:
            print(json.dumps(res, indent=2))
    except Exception as e:
        print(f"FATAL: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
