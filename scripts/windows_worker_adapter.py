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
    
    # 2. Wait for outbox result
    target_outbox_file = outbox / f"{task['task_id']}_result.json"
    
    timeout = 300
    start = time.time()
    
    while True:
        if target_outbox_file.exists():
            break
        if time.time() - start > timeout:
            print(f"[Windows Transport] Timeout waiting for Windows worker to complete task {task['task_id']}.")
            # Write a failed result
            res = {
                "status": "FAILED",
                "reason": "TIMEOUT",
                "goal_id": task.get("goal_id"),
                "task_id": task["task_id"]
            }
            with open(f"results/incoming/{task['task_id']}_result.json", 'w') as f:
                json.dump(res, f)
            return
            
        time.sleep(2)
        
    # 3. Post result to Courier Server
    print(f"[Windows Transport] Received result for {task['task_id']} from Windows Worker!")
    
    with open(target_outbox_file, 'r') as f:
        result_payload = json.load(f)
        
    import requests
    server_url = os.environ.get("COURIER_SERVER", "http://127.0.0.1:8080").rstrip("/")
    api_key = os.environ.get("COURIER_API_KEY", "")
    
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        
    try:
        resp = requests.post(f"{server_url}/tasks/result", json=result_payload, headers=headers, timeout=15)
        if resp.status_code >= 400:
            print(f"[Windows Transport] Courier result POST failed: {resp.status_code} {resp.text}")
        else:
            print(f"[Windows Transport] Successfully posted result to Courier Server.")
    except Exception as e:
        print(f"[Windows Transport] Error posting result: {e}")
    
    # Cleanup outbox
    os.remove(target_outbox_file)

if __name__ == "__main__":
    run(sys.argv[1])
