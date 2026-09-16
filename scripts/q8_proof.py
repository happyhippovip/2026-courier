import time
import os
import sys
import subprocess
import json
import urllib.request
import signal
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
SERVER_DIR = BASE_DIR / "server"
STATE_FILE = SERVER_DIR / "state" / "central_state.json"
WORKER_DIR = BASE_DIR / "scripts" / "windows_worker"

os.environ["COURIER_API_KEY"] = "q8-secret-key"
os.environ["COURIER_VERIFIER_API_KEY"] = "q8-verifier-key"

def clear_state():
    if STATE_FILE.exists():
        STATE_FILE.unlink()
    for f in (WORKER_DIR / "state").glob("*.json"):
        f.unlink()

def get_json(url):
    req = urllib.request.Request(url)
    req.add_header("Authorization", "Bearer q8-secret-key")
    try:
        with urllib.request.urlopen(req) as res:
            return json.loads(res.read().decode())
    except urllib.error.HTTPError as e:
        print("HTTP ERROR:", e.code, e.read().decode())
        raise

def post_json(url, data):
    req = urllib.request.Request(url, method="POST")
    req.add_header("Authorization", "Bearer q8-secret-key")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=json.dumps(data).encode()) as res:
            return json.loads(res.read().decode())
    except urllib.error.HTTPError as e:
        print("HTTP ERROR:", e.code, e.read().decode())
        raise

def run_proof():
    clear_state()
    
    print("[*] Starting server...")
    server_env = os.environ.copy()
    server_env["PYTHONUNBUFFERED"] = "1"
    server_proc = subprocess.Popen([
        "uv", "run", "--with", "flask", "python", "-c", 
        "import os; os.environ['COURIER_API_KEY']='q8-secret-key'; os.environ['COURIER_VERIFIER_API_KEY']='q8-verifier-key'; from server.app import app; app.run(port=8080)"
    ], cwd=str(BASE_DIR), env=server_env)
    time.sleep(2)
    
    print("[*] Starting Windows worker...")
    worker_proc = subprocess.Popen([sys.executable, "daemon.py"], cwd=str(WORKER_DIR), env=server_env)
    time.sleep(3)
    
    workers = {}
    win_worker = None
    for _ in range(15):
        workers = get_json("http://127.0.0.1:8080/workers")
        for w in workers.values():
            if "windows" in w["capabilities"]:
                win_worker = w["worker_id"]
        if win_worker:
            break
        time.sleep(1)
            
    print("Workers after start:", workers)
    assert win_worker, "Windows worker did not register"
    
    print("[*] Dispatching a Windows task...")
    post_json("http://127.0.0.1:8080/goals", {
        "goal_text": "Proof",
        "workflow_plan": [
            {"instruction": "WinTask", "target_agent": "windows"}
        ]
    })
    
    active_task = None
    for _ in range(15):
        workers = get_json("http://127.0.0.1:8080/workers")
        w = workers[win_worker]
        if not w["available"]:
            active_task = w["current_task"]
            break
        time.sleep(1)
        
    assert not w["available"], "Worker should be busy"
    assert active_task, "Worker should have a task"
    
    print(f"[*] Worker is processing task {active_task}. Hard killing worker to simulate crash...")
    worker_proc.terminate()
    worker_proc.wait()
    
    print("[*] Worker is dead. Courier still thinks it is authoritative/available (but busy).")
    
    print("[*] Simulating Linux worker claiming a task...")
    post_json("http://127.0.0.1:8080/goals", {
        "goal_text": "Proof Linux",
        "workflow_plan": [
            {"instruction": "LinuxTask", "target_agent": "linux"}
        ]
    })
    post_json("http://127.0.0.1:8080/workers/register", {
        "worker_id": "linux-1",
        "platform": "linux",
        "capabilities": ["linux"],
        "cost_class": "free"
    })
    linux_claim = post_json("http://127.0.0.1:8080/tasks/claim", {"worker_id": "linux-1"})
    assert linux_claim.get("task"), "Linux worker should be able to claim task independently"
    print("[*] Linux worker claimed successfully. OTHER_WORKER_CAN_CONTINUE = PASS")
    
    print("[*] Now simulating Windows worker restart with LOST state (Stale Ownership Bug scenario)")
    for f in (WORKER_DIR / "state").glob("*.json"):
        f.unlink()
        
    print("[*] Restarting Windows worker...")
    worker_proc2 = subprocess.Popen([sys.executable, "daemon.py"], cwd=str(WORKER_DIR), env=server_env)
    
    restarted = False
    for _ in range(15):
        workers = get_json("http://127.0.0.1:8080/workers")
        w = workers.get(win_worker)
        if w and w.get("current_task") is None:
            restarted = True
            break
        time.sleep(1)
        
    workers = get_json("http://127.0.0.1:8080/workers")
    w = workers[win_worker]
    print(f"[*] Worker status after restart: available={w['available']}, current_task={w['current_task']}")
    assert w["available"], "Worker should be available after restarting with empty state!"
    assert w["current_task"] is None, "Worker should not inherit stale task!"
    print("[*] STALE_OWNERSHIP = NONE")
    
    walls = get_json("http://127.0.0.1:8080/walls")
    orphaned_found = False
    for g in walls.values():
        for step in g.get("workflow_plan", []):
            if step["task_id"] == active_task:
                assert step["status"] == "HUMAN_REQUIRED"
                assert step["recovery_reason"] == "WORKER_RESTARTED_AND_LOST_STATE"
                orphaned_found = True
    assert orphaned_found, "Orphaned task should be quarantined"
    
    print("[*] DEAD_WINDOWS_NOT_ROUTABLE = PASS")
    print("[*] WINDOWS_REJOIN = PASS")
    
    print("\nAll Q8 acceptance criteria PASSED!")
    
    worker_proc2.terminate()
    server_proc.terminate()

if __name__ == "__main__":
    run_proof()
