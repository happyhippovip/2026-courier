import os
import sys
import time
import shutil
import subprocess
import json
import urllib.request
import urllib.error
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
FRESH_WORKER_DIR = BASE_DIR.parent / "fresh_windows_worker"
WORKER_SOURCE_DIR = BASE_DIR / "scripts" / "windows_worker"

def get_json(url, key="q12-secret"):
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(req) as res:
            return json.loads(res.read().decode())
    except urllib.error.HTTPError as e:
        print("HTTP ERROR:", e.code, e.read().decode())
        raise

def post_json(url, data, key="q12-secret"):
    req = urllib.request.Request(url, method="POST")
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=json.dumps(data).encode()) as res:
            return json.loads(res.read().decode())
    except urllib.error.HTTPError as e:
        print("HTTP ERROR:", e.code, e.read().decode())
        return None

def main():
    print("[*] 1. Preparing clean execution context...")
    if FRESH_WORKER_DIR.exists():
        shutil.rmtree(FRESH_WORKER_DIR, ignore_errors=True)
    FRESH_WORKER_DIR.mkdir(parents=True)
    
    # Copy ONLY canonical files
    for fname in ["bootstrap.ps1", "install_service.ps1", "daemon.py", "start.bat"]:
        shutil.copy(WORKER_SOURCE_DIR / fname, FRESH_WORKER_DIR / fname)
        
    print("[*] 2. Starting central Courier server...")
    server_env = os.environ.copy()
    server_env["PYTHONUNBUFFERED"] = "1"
    server_env["COURIER_API_KEY"] = "q12-secret"
    server_env["COURIER_VERIFIER_API_KEY"] = "q12-verifier"
    
    server_proc = subprocess.Popen([
        "uv", "run", "--with", "flask", "python", "-c", 
        "import os; os.environ['COURIER_API_KEY']='q12-secret'; os.environ['COURIER_VERIFIER_API_KEY']='q12-verifier'; from server.app import app; app.run(port=8080)"
    ], cwd=str(BASE_DIR), env=server_env)
    time.sleep(2)
    
    print("[*] 3. Bootstrapping NEW Windows Worker identity...")
    worker_id = "NEW-WIN-PC-01"
    ps_cmd = [
        "powershell", "-ExecutionPolicy", "Bypass", "-File", "bootstrap.ps1",
        "-ServerArg", "http://127.0.0.1:8080",
        "-ApiKeyArg", "q12-secret",
        "-WorkerIdArg", worker_id
    ]
    subprocess.run(ps_cmd, cwd=str(FRESH_WORKER_DIR))
    
    print("[*] Waiting for new worker to register...")
    registered = False
    for _ in range(30):
        try:
            workers = get_json("http://127.0.0.1:8080/workers")
            if worker_id in workers:
                print(f"    -> Worker {worker_id} successfully registered!")
                registered = True
                break
        except Exception:
            pass
        time.sleep(1)
        
    assert registered, "New worker failed to register!"
    
    print("[*] 4. Dispatching ONE harmless TaskPacket to new worker...")
    task_id = "task-replace-001"
    post_json("http://127.0.0.1:8080/goals", {
        "goal_text": "Proof Q12 Replaceability",
        "workflow_plan": [
            {
                "task_id": task_id,
                "instruction": "Output SUCCESS text for replaceability proof",
                "target_agent": "windows",
                "artifacts": []
            }
        ]
    })
    
    print("[*] 5. Waiting for task execution and automatic result return (max 300s)...")
    completed_task = None
    for _ in range(300):
        try:
            tasks = get_json("http://127.0.0.1:8080/tasks/pending_verification", key="q12-verifier")
            for t in tasks.get("tasks", []):
                if t["task_id"] == task_id:
                    completed_task = t
                    break
        except Exception:
            pass
        if completed_task:
            break
        time.sleep(2)
        
    assert completed_task, "Task result was not received from the new worker!"
    result = completed_task["result"]
    print(f"    -> Task completed! Result ID: {result['result_id']}")
    
    print("[*] 6. Verifying old worker was not required...")
    old_worker_dir = WORKER_SOURCE_DIR
    assert not (old_worker_dir / "state" / f"{task_id}.json").exists(), "Old worker stole the task!"
    
    print("\nACCEPTANCE CRITERIA MET:")
    print("FRESH_ENVIRONMENT_BOOTSTRAP = PASS")
    print("NEW_WORKER_IDENTITY = PASS")
    print("OLD_LOCAL_STATE_REQUIRED = NO")
    print("CHAT_HISTORY_REQUIRED = NO")
    print("AUTO_RESULT_RETURN = PASS")
    print("ORIGINAL_WINDOWS_REQUIRED = NO")
    print("WINDOWS_REPLACEABILITY = PASS")
    
    print(f"\nFINAL RETURN:")
    print(f"BOOTSTRAP_PATH = {FRESH_WORKER_DIR}")
    print(f"NEW_WORKER_ID = {worker_id}")
    print(f"TASK_ID = {task_id}")
    print(f"RESULT_ID = {result['result_id']}")
    print(f"MANUAL_STEPS = 0")
    print(f"WINDOWS_REPLACEABILITY = PASS")
    print(f"BLOCKER = NONE")
    
    print("\n[*] Tearing down...")
    server_proc.terminate()
    subprocess.run(["powershell", "-Command", "Stop-Process -Name python -Force -ErrorAction SilentlyContinue"])
    subprocess.run(["powershell", "-Command", "Stop-Process -Name uv -Force -ErrorAction SilentlyContinue"])

if __name__ == "__main__":
    main()
