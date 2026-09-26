import json, sys, os, time, shutil, requests
from typing import Any
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def post_result(result: dict[str, Any]) -> None:
    key = os.environ.get("COURIER_API_KEY")
    if not key:
        print("[Mac Transport] Warning: COURIER_API_KEY not set, cannot post result.", file=sys.stderr)
        return
    url = os.environ.get("COURIER_SERVER", "http://127.0.0.1:8080").rstrip("/") + "/tasks/result"
    response = requests.post(
        url,
        json=result,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        timeout=15,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Courier result POST failed: {response.status_code} {response.text}")

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
                "task_id": task["task_id"],
                "attempt_id": task.get("attempt_id"),
                "dispatch_id": task.get("dispatch_id"),
                "worker_id": task.get("worker_id"),
                "result_id": f"result-{task.get('dispatch_id', task['task_id'])}-timeout",
            }
            res["artifacts"] = []
            res["provider"] = "mac_timeout"
            res["raw_result"] = {"reason": "TIMEOUT"}
            post_result(res)
            return
            
        time.sleep(2)
        
    print(f"[Mac Transport] Received result for {task['task_id']} from Mac Worker!")
    with open(target_outbox_file, 'r') as f:
        res = json.load(f)
    post_result(res)
    os.remove(target_outbox_file)

if __name__ == "__main__":
    run(sys.argv[1])
