import hashlib
import json
import sys
import subprocess
import os
import time
from datetime import datetime, timezone

STATE_FILE = 'central_state.json'
WORKFLOW = 'revenue_v1_baseline.yml'
# Clock skew allowance when matching our dispatch to a GitHub run timestamp.
RUN_MATCH_SKEW_SECONDS = 30


def _load_state(state_file):
    """Load central state, or fail closed.

    A corrupt/unreadable state file must NOT silently reset to empty: that
    would orphan already-admitted tasks and cause duplicate dispatches.
    Returns (state, error). error is None on success.
    """
    if not os.path.exists(state_file):
        return {"tasks": {}}, None
    try:
        with open(state_file, 'r') as f:
            state = json.load(f)
        if not isinstance(state, dict):
            return None, f"{state_file} does not contain a JSON object"
        state.setdefault("tasks", {})
        return state, None
    except Exception as e:
        return None, f"refusing to dispatch: cannot read {state_file}: {e}"


def _find_dispatched_run(dispatch_start_epoch, workflow=WORKFLOW):
    """Return the databaseId of the run created for our dispatch, or "".

    Never uses `gh run list --limit 1`: under concurrent intakes the newest
    run may belong to a different intake, which would misbind execution_ref.
    Instead, take recent runs with creation timestamps and pick the earliest
    run created at/after our dispatch start (minus a small skew allowance).
    """
    try:
        proc = subprocess.run(
            ["gh", "run", "list", f"--workflow={workflow}", "--limit=10",
             "--json", "databaseId,createdAt"],
            capture_output=True, text=True, check=True, timeout=60)
    except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired) as e:
        print(f"Warning: could not list workflow runs: {e}")
        return ""
    try:
        runs = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return ""
    candidates = []
    for run in runs:
        try:
            created = datetime.fromisoformat(
                str(run.get("createdAt", "")).replace("Z", "+00:00"))
            created_epoch = created.replace(tzinfo=timezone.utc).timestamp() \
                if created.tzinfo is None else created.timestamp()
        except (ValueError, TypeError):
            continue
        if created_epoch >= dispatch_start_epoch - RUN_MATCH_SKEW_SECONDS:
            candidates.append((created_epoch, run.get("databaseId")))
    if not candidates:
        return ""
    candidates.sort()
    return str(candidates[0][1])


def dispatch_intake(intake_file):
    with open(intake_file, 'r') as f:
        intake = json.load(f)

    customer_reference = intake.get('customer_reference')
    if not customer_reference:
        print("Refusing to dispatch intake without customer_reference")
        return 2

    # Deterministic task identity: re-admitting the same intake file must not
    # create a second task (duplicate execution). Same 8-hex format as before.
    task_id = "task-revenue-" + hashlib.sha256(
        customer_reference.encode("utf-8")).hexdigest()[:8]
    print(f"Admitting intake {customer_reference} as {task_id}")

    # Idempotent admit: already-admitted intake skips re-dispatch entirely.
    state, error = _load_state(STATE_FILE)
    if error is not None:
        print(error)
        return 1
    if task_id in state["tasks"]:
        print(f"Intake {customer_reference} already admitted as {task_id}; "
              f"skipping re-dispatch.")
        return 0

    # Revenue V1 uses GitHub Actions as the primary qualified lane
    dispatch_start = time.time()
    cmd = [
        "gh", "workflow", "run", WORKFLOW,
        "-f", f"target_owner={intake['target_owner']}",
        "-f", f"target_repo={intake['target_repo']}",
        "-f", f"target_sha={intake['target_sha']}",
        "-f", f"customer_reference={intake['customer_reference']}",
        "-f", f"price_currency={intake.get('price_currency', 'EUR_99')}",
        "-f", f"delivery_destination={intake.get('delivery_destination', 'none')}"
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"Successfully dispatched to GitHub Actions worker.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to dispatch: {e.stderr}")
        return 1

    # Find the execution_ref (the GitHub run ID).
    # We pause a tiny bit so GitHub registers the workflow dispatch.
    time.sleep(3)
    execution_ref = _find_dispatched_run(dispatch_start)

    # Update Central State
    state["tasks"][task_id] = {
        "task_id": task_id,
        "customer_reference": intake['customer_reference'],
        "worker_id": "github-actions-revenue-v1",
        "platform": "github",
        "dispatch_ref": "intake_dispatcher_local",
        "execution_ref": execution_ref if execution_ref else "DISPATCHED",
        "state": "DISPATCHED_TO_EXTERNAL",
        "last_transition": "AUTOMATIC_DISPATCH",
        "next_explicit_transition": "WAIT_FOR_GITHUB_PR",
        "real_wall": "HUMAN_REVIEW_REQUIRED_ON_PR"
    }

    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

    print(f"Central state updated. System chain fully connected for intake -> execution -> PR.")
    return 0

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/intake_dispatcher.py <intake_file.json>")
        sys.exit(1)
    sys.exit(dispatch_intake(sys.argv[1]))
