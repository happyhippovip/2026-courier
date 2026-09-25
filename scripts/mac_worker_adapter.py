import json, sys, os, time, shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

def run(task_file, root=None):
    # Transport dirs are anchored at the repo root, never at the
    # caller's cwd: a foreign cwd previously scattered inbox/outbox
    # and the delivered result outside the repo (lost-result risk).
    root = Path(root) if root is not None else REPO_ROOT
    with open(task_file, 'r') as f:
        task = json.load(f)
        
    print(f"[Mac Transport] Routing task {task['task_id']} to Mac Worker DualTransport...")
    
    base_dir = root / "scripts" / "mac_worker"
    inbox = base_dir / "inbox"
    outbox = base_dir / "outbox"
    
    inbox.mkdir(parents=True, exist_ok=True)
    outbox.mkdir(parents=True, exist_ok=True)
    
    # Check if task explicitly needs native or AI
    # if not specified, default to ANTIGRAVITY for now, or detect based on some keyword.
    
    target_inbox_file = inbox / f"{task['task_id']}.json"
    shutil.copy(task_file, target_inbox_file)
    
    print(f"[Mac Transport] Task {task['task_id']} dropped in {target_inbox_file}. Waiting for result...")
    
    target_outbox_file = outbox / f"{task['task_id']}_result.json"
    timeout = 300
    start = time.time()
    
    while True:
        if target_outbox_file.exists():
            break
        if time.time() - start > timeout:
            print(f"[Mac Transport] Timeout waiting for Mac worker to complete task {task['task_id']}.")
            res = {
                "status": "FAILED",
                "reason": "TIMEOUT",
                "goal_id": task.get("goal_id"),
                "task_id": task["task_id"]
            }
            incoming_dir = root / "results" / "incoming"
            incoming_dir.mkdir(parents=True, exist_ok=True)
            with open(incoming_dir / f"{task['task_id']}_result.json", 'w') as f:
                json.dump(res, f)
            return
            
        time.sleep(2)
        
    print(f"[Mac Transport] Received result for {task['task_id']} from Mac Worker!")
    incoming_dir = root / "results" / "incoming"
    incoming_dir.mkdir(parents=True, exist_ok=True)
    incoming = incoming_dir / f"{task['task_id']}_result.json"
    incoming_tmp = incoming.with_suffix(".json.tmp")
    shutil.copy(target_outbox_file, incoming_tmp)
    os.replace(incoming_tmp, incoming)
    os.remove(target_outbox_file)

if __name__ == "__main__":
    run(sys.argv[1])
