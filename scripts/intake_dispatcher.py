import json
import sys
import uuid
import os
import requests

API_URL = os.environ.get("COURIER_SERVER", "http://127.0.0.1:8080").rstrip("/")
API_KEY = os.environ.get("COURIER_API_KEY", "")
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

def dispatch_intake(intake_file):
    with open(intake_file, 'r') as f:
        intake = json.load(f)

    task_id = f"task-revenue-{uuid.uuid4().hex[:8]}"
    goal_id = f"REVENUE-GOAL-{uuid.uuid4().hex[:8].upper()}"
    print(f"Admitting intake {intake.get('customer_reference')} as {task_id}")

    goal_payload = {
        "goal_id": goal_id,
        "goal_text": f"Revenue Safety Audit for {intake.get('target_owner', 'unknown')}/{intake.get('target_repo', 'unknown')}",
        "workflow_plan": [
            {
                "task_id": task_id,
                "type": "revenue_safety_audit",
                "capabilities": ["revenue_safety_audit"],
                "target_owner": intake.get('target_owner'),
                "target_repo": intake.get('target_repo'),
                "target_sha": intake.get('target_sha'),
                "customer_reference": intake.get('customer_reference'),
                "price_currency": intake.get('price_currency', 'EUR_99'),
                "delivery_destination": intake.get('delivery_destination', 'none'),
                "dependencies": [],
                "status": "QUEUED",
                "target_agent": "linux",
                "idempotency_key": task_id
            }
        ]
    }

    print(f"Submitting customer intake goal: {goal_id}")
    try:
        res = requests.post(f"{API_URL}/goals", json=goal_payload, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            print(f"Success! Intake admitted to Motor via API. Goal ID: {goal_id}")
        else:
            print(f"Failed to submit intake: HTTP {res.status_code} - {res.text}")
            sys.exit(1)
    except Exception as e:
        print(f"Error submitting intake to API: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/intake_dispatcher.py <intake_file.json>")
        sys.exit(1)
    dispatch_intake(sys.argv[1])

