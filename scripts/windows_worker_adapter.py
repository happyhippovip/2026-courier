import json, sys, os, time, shutil
from pathlib import Path

def run(task_file):
    with open(task_file, 'r') as f:
        task = json.load(f)
        
    print(f"[Windows Transport] Routing task {task['task_id']} to Windows Worker DualTransport...")
    
    # Define transport directories
    base_dir = Path("scripts/windows_worker")
    inbox = base_dir / "inbox"
    outbox = base_dir / "outbox"
    
    inbox.mkdir(parents=True, exist_ok=True)
    outbox.mkdir(parents=True, exist_ok=True)
    
    # 1. Drop into inbox
    target_inbox_file = inbox / f"{task['task_id']}.json"
    shutil.copy(task_file, target_inbox_file)
    
    print(f"[Windows Transport] Task {task['task_id']} dropped in {target_inbox_file}. Waiting for result...")
    
    # 2. Wait for outbox result using heartbeats
    target_outbox_file = outbox / f"{task['task_id']}_result.json"
    claimed_inbox_file = inbox / f"{task['task_id']}.json.claimed"
    target_inbox_file = inbox / f"{task['task_id']}.json"
    
    while True:
        if target_outbox_file.exists():
            break
            
        # Check if daemon is still working on it (lease)
        is_working = False
        if claimed_inbox_file.exists():
            if time.time() - claimed_inbox_file.stat().st_mtime < 120:
                is_working = True
        elif target_inbox_file.exists():
            is_working = True # Still waiting to be picked up
            
        if not is_working:
            print(f"[Windows Transport] Lease expired or task lost for {task['task_id']}.")
            # Write a failed result with worker_id so it doesn't crash verification
            res = {
                "status": "FAILED",
                "reason": "LEASE_EXPIRED",
                "goal_id": task.get("goal_id"),
                "task_id": task["task_id"],
                "worker_id": "WINDOWS-01",  # Need to include worker_id for contract
                "run_id": "adapter-lease-expiry"
            }
            with open(f"results/incoming/{task['task_id']}_result.json", 'w') as f:
                json.dump(res, f)
            return
            
        time.sleep(2)
        
    # 3. Copy result to control plane's incoming directory
    print(f"[Windows Transport] Received result for {task['task_id']} from Windows Worker!")
    os.makedirs("results/incoming", exist_ok=True)
    incoming = Path(f"results/incoming/{task['task_id']}_result.json")
    incoming_tmp = incoming.with_suffix(".json.tmp")
    shutil.copy(target_outbox_file, incoming_tmp)
    os.replace(incoming_tmp, incoming)
    
    # Cleanup outbox
    os.remove(target_outbox_file)

if __name__ == "__main__":
    run(sys.argv[1])
