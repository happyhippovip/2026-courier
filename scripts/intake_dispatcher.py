import json
import sys
import time
import uuid
import subprocess
import os
from datetime import datetime

# Marker recorded when no single run can be unambiguously bound to this
# dispatch. Downstream must treat it as "linkage pending reconcile",
# never as a run ID. (M05-Q1: take-latest `gh run list --limit 1` could
# attach a foreign run under concurrent dispatches.)
UNBOUND_EXECUTION_REF = "DISPATCHED_UNBOUND"

# Bounded wait for GitHub to register the dispatched run.
BIND_ATTEMPTS = 3
BIND_RETRY_DELAY_SECONDS = 2


def _parse_created_at(value):
    try:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text).timestamp()
    except (ValueError, TypeError):
        return None


def resolve_execution_ref(workflow, since_epoch, attempts=BIND_ATTEMPTS,
                          delay=BIND_RETRY_DELAY_SECONDS):
    """Return the databaseId of the single run created after since_epoch.

    Returns None when zero or more than one candidate run exists
    (ambiguous: concurrent dispatch or API lag) or when `gh` fails.
    Callers must fail closed on None, never fall back to take-latest.
    """
    for attempt in range(max(1, attempts)):
        try:
            run_info = subprocess.run(
                ["gh", "run", "list", f"--workflow={workflow}",
                 "--limit=10", "--json", "databaseId,createdAt"],
                capture_output=True, text=True)
            runs = json.loads(run_info.stdout or "[]")
        except (subprocess.CalledProcessError, ValueError):
            runs = []
        candidates = []
        if isinstance(runs, list):
            for run in runs:
                if not isinstance(run, dict):
                    continue
                created = _parse_created_at(run.get("createdAt"))
                if created is not None and created >= since_epoch:
                    candidates.append(str(run.get("databaseId")))
        if len(candidates) == 1:
            return candidates[0]
        if attempt < max(1, attempts) - 1:
            time.sleep(delay)
    return None


def dispatch_intake(intake_file):
    with open(intake_file, 'r') as f:
        intake = json.load(f)
        
    task_id = f"task-revenue-{uuid.uuid4().hex[:8]}"
    print(f"Admitting intake {intake.get('customer_reference')} as {task_id}")
    
    # Revenue V1 uses GitHub Actions as the primary qualified lane
    cmd = [
        "gh", "workflow", "run", "revenue_v1_baseline.yml",
        "-f", f"target_owner={intake['target_owner']}",
        "-f", f"target_repo={intake['target_repo']}",
        "-f", f"target_sha={intake['target_sha']}",
        "-f", f"customer_reference={intake['customer_reference']}",
        "-f", f"price_currency={intake.get('price_currency', 'EUR_99')}",
        "-f", f"delivery_destination={intake.get('delivery_destination', 'none')}"
    ]
    
    # Timestamp BEFORE dispatch: our own run is created after this point,
    # so any other run created after it is a concurrent dispatch and makes
    # binding ambiguous -> UNBOUND (never a foreign run ID).
    dispatch_start = time.time()
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"Successfully dispatched to GitHub Actions worker.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to dispatch: {e.stderr}")
        sys.exit(1)
        
    # Bind the execution_ref (the GitHub run ID) to THIS dispatch only:
    # exactly one run created after dispatch_start binds, anything else
    # (zero, several, gh failure) fails closed to UNBOUND.
    execution_ref = resolve_execution_ref(
        "revenue_v1_baseline.yml", dispatch_start) or UNBOUND_EXECUTION_REF
    
    # Update Central State
    state_file = 'central_state.json'
    try:
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                state = json.load(f)
        else:
            state = {"tasks": {}}
    except Exception:
        state = {"tasks": {}}
        
    state["tasks"][task_id] = {
        "task_id": task_id,
        "customer_reference": intake['customer_reference'],
        "worker_id": "github-actions-revenue-v1",
        "platform": "github",
        "dispatch_ref": "intake_dispatcher_local",
        "execution_ref": execution_ref,
        "state": "DISPATCHED_TO_EXTERNAL",
        "last_transition": "AUTOMATIC_DISPATCH",
        "next_explicit_transition": "WAIT_FOR_GITHUB_PR",
        "real_wall": "HUMAN_REVIEW_REQUIRED_ON_PR"
    }
    
    with open(state_file, 'w') as f:
        json.dump(state, f, indent=2)
        
    print(f"Central state updated. System chain fully connected for intake -> execution -> PR.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/intake_dispatcher.py <intake_file.json>")
        sys.exit(1)
    dispatch_intake(sys.argv[1])
