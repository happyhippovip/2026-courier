import json
import sys
import uuid
import subprocess
import os

def dispatch_intake(intake_file):
    with open(intake_file, 'r') as f:
        intake = json.load(f)
        
    task_id = intake.get("task_id")
    if not task_id:
        if intake.get("customer_reference"):
            clean_ref = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(intake["customer_reference"]))
            task_id = f"task-revenue-{clean_ref}"
        else:
            import hashlib
            content_hash = hashlib.sha256(json.dumps(intake, sort_keys=True).encode('utf-8')).hexdigest()[:8]
            task_id = f"task-revenue-{content_hash}"
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
    
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"Successfully dispatched to GitHub Actions worker.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to dispatch: {e.stderr}")
        sys.exit(1)
        
    # Find the execution_ref safely
    # Under concurrency, `limit=1` binds the wrong run. We omit the guesswork.
    # The worker will report its true execution_ref upon result delivery.
    execution_ref = "DISPATCHED_PENDING_EXACT_BINDING"
    
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
