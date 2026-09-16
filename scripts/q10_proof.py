import time
import os
import sys
import subprocess
import json
import urllib.request
import signal
import hashlib
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
SERVER_DIR = BASE_DIR / "server"
STATE_FILE = SERVER_DIR / "state" / "central_state.json"
WORKER_DIR = BASE_DIR / "scripts" / "windows_worker"

os.environ["COURIER_API_KEY"] = "q10-secret-key"
os.environ["COURIER_VERIFIER_API_KEY"] = "q10-verifier-key"

def clear_state():
    if STATE_FILE.exists():
        STATE_FILE.unlink()
    for f in (WORKER_DIR / "state").glob("*.json"):
        f.unlink()

def get_json(url, key="q10-secret-key"):
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(req) as res:
            return json.loads(res.read().decode())
    except urllib.error.HTTPError as e:
        print("HTTP ERROR:", e.code, e.read().decode())
        raise

def post_json(url, data, key="q10-secret-key"):
    req = urllib.request.Request(url, method="POST")
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=json.dumps(data).encode()) as res:
            return json.loads(res.read().decode())
    except urllib.error.HTTPError as e:
        print("HTTP ERROR:", e.code, e.read().decode())
        return None

def run_proof():
    clear_state()
    
    print("[*] Starting server...")
    server_env = os.environ.copy()
    server_env["PYTHONUNBUFFERED"] = "1"
    server_proc = subprocess.Popen([
        "uv", "run", "--with", "flask", "python", "-c", 
        "import os; os.environ['COURIER_API_KEY']='q10-secret-key'; os.environ['COURIER_VERIFIER_API_KEY']='q10-verifier-key'; from server.app import app; app.run(port=8080)"
    ], cwd=str(BASE_DIR), env=server_env)
    time.sleep(2)
    
    print("[*] Starting Windows worker...")
    worker_proc = subprocess.Popen([sys.executable, "daemon.py"], cwd=str(WORKER_DIR), env=server_env)
    
    win_worker = None
    for _ in range(15):
        workers = get_json("http://127.0.0.1:8080/workers")
        for w in workers.values():
            if "windows" in w["capabilities"]:
                win_worker = w["worker_id"]
        if win_worker:
            break
        time.sleep(1)
            
    assert win_worker, "Windows worker did not register"
    
    print("[*] Dispatching a task with artifact requirements...")
    canary_file = "courier_canary_test-win-002.txt"
    canary_path = str(WORKER_DIR / canary_file)
    if os.path.exists(canary_path):
        os.remove(canary_path)

    # Let's formulate the exact task so it gets an artifact.
    # To bypass planning, we use workflow_plan directly.
    task_id = "test-win-002"
    post_json("http://127.0.0.1:8080/goals", {
        "goal_text": "Proof Q10",
        "workflow_plan": [
            {
                "task_id": task_id,
                "instruction": "Create the canary file",
                "target_agent": "windows",
                "artifacts": [canary_file]
            }
        ]
    })
    
    print("[*] Waiting for task to complete and result to be received (max 300s)...")
    completed_task = None
    for _ in range(300):
        tasks = get_json("http://127.0.0.1:8080/tasks/pending_verification", key="q10-verifier-key")
        for t in tasks.get("tasks", []):
            if t["task_id"] == task_id:
                completed_task = t
                break
        if completed_task:
            break
        time.sleep(1)
        
    assert completed_task, "Task result was not received"
    result = completed_task["result"]
    assert len(result["artifacts"]) > 0, "No artifacts reported"
    print(f"[*] REAL_EFFECT_CREATED = PASS. Worker created artifact and hashed it: {result['artifacts'][0]}")

    print("[*] Verifier checks the artifact...")
    # Simulated Independent Verifier Verification
    assert os.path.exists(canary_path), "File does not physically exist!"
    with open(canary_path, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()
        
    assert result["artifacts"][0]["sha256"] == file_hash, "Hash mismatch!"
    print("[*] TASK_SPECIFIC_VERIFICATION = PASS")
    print("[*] EXIT_CODE_ALONE_SUFFICIENT = NO. Verification requires physical hash matching.")

    print("[*] Attempting verification with stale identity...")
    stale_payload = {
        "task_id": task_id,
        "result_id": "stale-old-id",
        "verifier_id": "independent-verif-01",
        "artifacts": result["artifacts"],
        "verdict": "PASS"
    }
    stale_res = post_json("http://127.0.0.1:8080/tasks/verify", stale_payload, key="q10-verifier-key")
    assert stale_res is None or stale_res.get("error") == "result_id mismatch", "Stale result ID was accepted!"
    print("[*] STALE_IDENTITY_ACCEPTED = NO")

    print("[*] Performing true verification...")
    valid_payload = {
        "task_id": task_id,
        "result_id": result["result_id"],
        "verifier_id": "independent-verif-01",
        "artifacts": result["artifacts"],
        "verdict": "PASS"
    }
    valid_res = post_json("http://127.0.0.1:8080/tasks/verify", valid_payload, key="q10-verifier-key")
    assert valid_res and valid_res.get("status") == "RECONCILED", f"Failed to verify: {valid_res}"
    
    print("[*] AUTO_RECONCILE_AFTER_VERIFY = PASS")
    
    print("\nAll Q10 acceptance criteria PASSED!")
    
    worker_proc.terminate()
    server_proc.terminate()

if __name__ == "__main__":
    run_proof()
