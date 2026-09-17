#!/usr/bin/env python3
import os
import sys
import json
import uuid
import requests

API_URL = os.environ.get("COURIER_SERVER", "http://127.0.0.1:8080").rstrip("/")
API_KEY = os.environ.get("COURIER_API_KEY")
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

def submit_intake(owner: str, repo: str, sha: str, customer_ref: str):
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
                "idempotency_key": task_id
            }
        ]
    }
    
    print(f"Submitting customer intake goal: {goal_id} for {owner}/{repo}")
    res = requests.post(f"{API_URL}/goals", json=goal_payload, headers=HEADERS, timeout=10)
    if res.status_code == 200:
        print("Success!")
    else:
        print(f"Failed: {res.status_code} {res.text}")

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: python3 revenue_customer_intake.py <owner> <repo> <sha> <customer_ref>")
        sys.exit(1)
    if not API_KEY:
        print("FATAL: Missing COURIER_API_KEY, refusing to submit intake.")
        sys.exit(1)
        
    submit_intake(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
