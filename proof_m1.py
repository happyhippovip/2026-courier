import os
import sys
import time
import subprocess
import json
import urllib.request
from pathlib import Path

def run_proof():
    print("[Proof M1] Starting Physical Acceptance Proof with Real Workers...")
    
    workspace = Path(os.getcwd())
    state_file = workspace / "m1_state.json"
    if state_file.exists(): state_file.unlink()
    
    server_env = os.environ.copy()
    server_env["COURIER_API_KEY"] = "test-key"
    server_env["COURIER_VERIFIER_API_KEY"] = "test-verifier-key"
    server_env["COURIER_STATE_FILE"] = str(state_file)
    
    server_proc = subprocess.Popen(
        [sys.executable, "-m", "flask", "--app", "server.app:app", "run", "--port", "8088"],
        env=server_env, stdout=sys.stdout, stderr=sys.stderr
    )
    
    time.sleep(2)
    
    verifier_env = server_env.copy()
    verifier_env["COURIER_SERVER"] = "http://127.0.0.1:8088"
    verifier_proc = subprocess.Popen(
        [sys.executable, "-u", "scripts/courier_verifier.py"],
        env=verifier_env, stdout=sys.stdout, stderr=sys.stderr
    )
    
    w1_env = server_env.copy()
    w1_env["COURIER_SERVER"] = "http://127.0.0.1:8088"
    w1_env["COURIER_WORKER_ID"] = "MAC-REAL-01"
    w1_env["POLL_INTERVAL_SECONDS"] = "1"
    w1_proc = subprocess.Popen(
        [sys.executable, "-u", "scripts/mac_worker/daemon.py"],
        env=w1_env, stdout=sys.stdout, stderr=sys.stderr
    )
    
    time.sleep(3)
    
    plan = []
    for i in range(10):
        plan.append({
            "task_id": f"t-m1-{i}",
            "target_agent": "mac",
            "instruction": f"touch courier_canary_t-m1-{i}.txt",
            "mode": "NATIVE",
            "artifacts": [f"courier_canary_t-m1-{i}.txt"]
        })
        
    goal_payload = {
        "goal_text": "M1 Physical Acceptance",
        "workflow_plan": plan,
        "terminal": True
    }
    
    req = urllib.request.Request(
        "http://127.0.0.1:8088/goals",
        data=json.dumps(goal_payload).encode(),
        headers={"Authorization": "Bearer test-key", "Content-Type": "application/json"},
        method="POST"
    )
    res = urllib.request.urlopen(req)
    goal_id = json.loads(res.read())["goal_id"]
    
    print(f"[Proof M1] Goal submitted: {goal_id}. Waiting for completion...")
    
    success = False
    for _ in range(60):
        try:
            with open(state_file, "r") as f:
                st = json.load(f)
                status = st["goals"].get(goal_id, {}).get("status")
                if status == "DONE":
                    success = True
                    break
        except Exception:
            pass
        time.sleep(1)
            
    server_proc.terminate()
    verifier_proc.terminate()
    w1_proc.terminate()
    
    if success:
        print("[Proof M1] PASS: 10 tasks completed by REAL workers.")
    else:
        print("[Proof M1] FAIL: Goal did not complete in time.")
        sys.exit(1)

if __name__ == "__main__":
    run_proof()
