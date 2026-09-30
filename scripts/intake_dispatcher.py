import json
import sys
import uuid
import subprocess
import shutil
import os

REQUIRED_INTAKE_FIELDS = ("target_owner", "target_repo", "target_sha", "customer_reference")

def _int_env(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default

def _float_env(name, default):
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default

def _env_config():
    # Read at call time so overrides set after import still apply.
    return {
        "workflow": os.environ.get("COURIER_INTAKE_WORKFLOW", "revenue_v1_baseline.yml"),
        "worker_id": os.environ.get("COURIER_INTAKE_WORKER_ID", "github-actions-revenue-v1"),
        "state_file": os.environ.get("COURIER_STATE_PATH", "central_state.json"),
        "currency": os.environ.get("COURIER_PRICE_CURRENCY", "EUR_99"),
        "lookup_attempts": _int_env("COURIER_INTAKE_LOOKUP_ATTEMPTS", 6),
        "lookup_poll_seconds": _float_env("COURIER_INTAKE_LOOKUP_POLL_SECONDS", 5),
    }

def _list_run_ids(cfg):
    """All known run IDs for the workflow; empty set on any transport error."""
    try:
        info = subprocess.run(
            ["gh", "run", "list", f"--workflow={cfg['workflow']}",
             "--limit=50", "--json", "databaseId", "-q", ".[].databaseId"],
            capture_output=True, text=True)
    except OSError:
        return set()
    if info.returncode != 0:
        return set()
    return {line.strip() for line in info.stdout.splitlines() if line.strip()}

def _await_new_run(cfg, before):
    """Bind the run that appeared after our dispatch, not take-latest.

    Take-latest cross-binds under concurrent dispatches. The before/after
    delta narrows the match to runs created by this dispatch; concurrent
    foreign runs can still collide in theory (exact binding would need a
    correlation input plus run-name support in the workflow, which is a
    shared-CI change owned elsewhere). Empty string = unknown, and the
    caller records the honest DISPATCHED fallback.
    """
    import time
    for _ in range(max(1, cfg["lookup_attempts"])):
        new = sorted(_list_run_ids(cfg) - before)
        if new:
            return new[0]
        time.sleep(max(0, cfg["lookup_poll_seconds"]))
    return ""

def dispatch_intake(intake_file):
    cfg = _env_config()
    if shutil.which("gh") is None:
        print("courier: gh CLI not found on PATH", file=sys.stderr)
        sys.exit(2)
    try:
        with open(intake_file, 'r') as f:
            intake = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"courier: intake {intake_file} unreadable: {e}", file=sys.stderr)
        sys.exit(3)
    if not isinstance(intake, dict):
        print(f"courier: intake {intake_file} is not a JSON object", file=sys.stderr)
        sys.exit(3)
    missing = [f for f in REQUIRED_INTAKE_FIELDS if not intake.get(f)]
    if missing:
        print(f"courier: intake {intake_file} missing required fields: {', '.join(missing)}",
              file=sys.stderr)
        sys.exit(3)

    task_id = f"task-revenue-{uuid.uuid4().hex[:8]}"
    print(f"Admitting intake {intake.get('customer_reference')} as {task_id}")
    # Snapshot before dispatch so the post-dispatch delta binds OUR run.
    run_before = _list_run_ids(cfg)
    
    # Revenue V1 uses GitHub Actions as the primary qualified lane
    cmd = [
        "gh", "workflow", "run", cfg["workflow"],
        "-f", f"target_owner={intake['target_owner']}",
        "-f", f"target_repo={intake['target_repo']}",
        "-f", f"target_sha={intake['target_sha']}",
        "-f", f"customer_reference={intake['customer_reference']}",
        "-f", f"price_currency={intake.get('price_currency', cfg['currency'])}",
        "-f", f"delivery_destination={intake.get('delivery_destination', 'none')}"
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"Successfully dispatched to GitHub Actions worker.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to dispatch: {e.stderr}")
        sys.exit(1)
        
    # Find the execution_ref (the GitHub run ID) via before/after delta.
    execution_ref = _await_new_run(cfg, run_before)

    # Update Central State
    state_file = cfg["state_file"]
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
        "worker_id": cfg["worker_id"],
        "platform": "github",
        "dispatch_ref": "intake_dispatcher_local",
        "execution_ref": execution_ref if execution_ref else "DISPATCHED",
        "state": "DISPATCHED_TO_EXTERNAL",
        "last_transition": "AUTOMATIC_DISPATCH",
        "next_explicit_transition": "WAIT_FOR_GITHUB_PR",
        "real_wall": "HUMAN_REVIEW_REQUIRED_ON_PR"
    }
    
    # Atomic write: a torn central_state.json breaks every later reader.
    tmp_state = state_file + ".tmp"
    with open(tmp_state, 'w') as f:
        json.dump(state, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_state, state_file)

    print(f"Central state updated. System chain fully connected for intake -> execution -> PR.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/intake_dispatcher.py <intake_file.json>")
        sys.exit(1)
    dispatch_intake(sys.argv[1])
