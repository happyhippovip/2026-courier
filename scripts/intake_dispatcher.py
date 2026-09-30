import json
import sys
import uuid
import subprocess
import shutil
import os

REQUIRED_INTAKE_FIELDS = ("target_owner", "target_repo", "target_sha", "customer_reference")

def _env_config():
    # Read at call time so overrides set after import still apply.
    return {
        "workflow": os.environ.get("COURIER_INTAKE_WORKFLOW", "revenue_v1_baseline.yml"),
        "worker_id": os.environ.get("COURIER_INTAKE_WORKER_ID", "github-actions-revenue-v1"),
        "state_file": os.environ.get("COURIER_STATE_PATH", "central_state.json"),
        "currency": os.environ.get("COURIER_PRICE_CURRENCY", "EUR_99"),
    }

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
        
    # Find the execution_ref (the GitHub run ID)
    # We pause a tiny bit so GitHub registers the workflow dispatch
    import time
    time.sleep(3)
    run_info = subprocess.run(["gh", "run", "list", f"--workflow={cfg['workflow']}", "--limit=1", "--json", "databaseId", "-q", ".[0].databaseId"], capture_output=True, text=True)
    execution_ref = run_info.stdout.strip()

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
    
    with open(state_file, 'w') as f:
        json.dump(state, f, indent=2)
        
    print(f"Central state updated. System chain fully connected for intake -> execution -> PR.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/intake_dispatcher.py <intake_file.json>")
        sys.exit(1)
    dispatch_intake(sys.argv[1])
