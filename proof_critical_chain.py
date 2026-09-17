import os
import sys
import time
import subprocess
import json
import urllib.request
from pathlib import Path

def run_proof():
    print("[Critical Chain Proof] Testing exact PR SHA 5a619fae8c3b776483895e0b4c6b4b9b36433160...")
    
    port = 8091
    workspace = Path(os.getcwd())
    state_file = workspace / "test_chain_state.json"
    if state_file.exists():
        state_file.unlink()
        
    server_env = os.environ.copy()
    server_env["COURIER_API_KEY"] = "test-secret-key"
    server_env["COURIER_VERIFIER_API_KEY"] = "test-verifier-key"
    server_env["COURIER_STATE_FILE"] = str(state_file)
    
    print(f"[Step 1: OS MOTOR ALIVE] Starting server on port {port}...")
    server_proc = subprocess.Popen(
        [sys.executable, "-m", "flask", "--app", "server.app:app", "run", "--port", str(port)],
        env=server_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    # Wait for server /health
    server_alive = False
    for _ in range(20):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as r:
                if r.status == 200:
                    server_alive = True
                    break
        except Exception:
            time.sleep(0.5)
            
    if not server_alive:
        server_proc.kill()
        out, _ = server_proc.communicate()
        print(f"Server failed to start. Logs:\n{out}")
        sys.exit(1)
    print("  -> OS MOTOR ALIVE: PASS")
    
    print("[Step 2: START INDEPENDENT VERIFIER]")
    verifier_env = server_env.copy()
    verifier_env["COURIER_SERVER"] = f"http://127.0.0.1:{port}"
    verifier_proc = subprocess.Popen(
        [sys.executable, "-u", "scripts/courier_verifier.py"],
        env=verifier_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    print("[Step 3: START REAL MAC WORKER]")
    worker_env = server_env.copy()
    worker_env["COURIER_SERVER"] = f"http://127.0.0.1:{port}"
    worker_env["COURIER_WORKER_ID"] = "MAC-CLI-PROOF-01"
    worker_env["POLL_INTERVAL_SECONDS"] = "1"
    worker_proc = subprocess.Popen(
        [sys.executable, "-u", "scripts/mac_worker/daemon.py"],
        env=worker_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    # Give worker time to register
    time.sleep(3)
    
    print("[Step 4: SUBMIT GOAL WITH 2-TASK DEPENDENCY CHAIN]")
    canary1 = "courier_canary_cli_01.txt"
    canary2 = "courier_canary_cli_02.txt"
    for c in [canary1, canary2]:
        if os.path.exists(c):
            os.remove(c)
        
    goal_payload = {
        "goal_text": "CLI Acceptance Proof Goal - 2 Tasks DAG",
        "workflow_plan": [
            {
                "task_id": "cli-task-01",
                "target_agent": "mac",
                "mode": "NATIVE",
                "instruction": f"touch {canary1}",
                "artifacts": [canary1]
            },
            {
                "task_id": "cli-task-02",
                "target_agent": "mac",
                "mode": "NATIVE",
                "instruction": f"touch {canary2}",
                "artifacts": [canary2],
                "depends_on": ["cli-task-01"]
            }
        ],
        "terminal": True
    }
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/goals",
        data=json.dumps(goal_payload).encode("utf-8"),
        headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
        method="POST"
    )
    res = urllib.request.urlopen(req)
    goal_id = json.loads(res.read())["goal_id"]
    print(f"  -> Goal submitted: {goal_id}")
    
    # Observe execution transitions
    print("[Step 5: OBSERVING TRANSITIONS (DAG: task1 -> reconcile -> READY task2 -> task2 reconcile -> GOAL DONE)]")
    task_status_seen = {}
    start_time = time.time()
    
    try:
        while time.time() - start_time < 20:
            if state_file.exists():
                try:
                    with open(state_file, "r") as f:
                        st = json.load(f)
                    for tid in ["cli-task-01", "cli-task-02"]:
                        task = st.get("tasks", {}).get(tid)
                        if task:
                            cur_status = task.get("status")
                            history = task_status_seen.get(tid, [])
                            if not history or history[-1] != cur_status:
                                history.append(cur_status)
                                task_status_seen[tid] = history
                                print(f"  -> {tid} transition: {cur_status}")
                    goal_status = st.get("goals", {}).get(goal_id, {}).get("status")
                    if goal_status == "DONE":
                        print("  -> GOAL STATUS: DONE!")
                        break
                except Exception:
                    pass
            time.sleep(0.5)
            
        print(f"\nObserved transitions: {task_status_seen}")
        
    finally:
        worker_proc.kill()
        verifier_proc.kill()
        server_proc.kill()
        w_out, _ = worker_proc.communicate()
        v_out, _ = verifier_proc.communicate()
        s_out, _ = server_proc.communicate()
        
    print("\n--- WORKER LOGS ---")
    print(w_out[-1500:] if len(w_out) > 1500 else w_out)
    
    print("\n--- VERIFIER LOGS ---")
    print(v_out[-1000:] if len(v_out) > 1000 else v_out)

if __name__ == "__main__":
    run_proof()
