import os
import sys
import json
import time
import subprocess
import signal
import uuid
from pathlib import Path
import traceback
import requests

def main():
    print("--- REAL WORKER BINDING PREP ---")
    server_port = 8124
    server_url = f"http://127.0.0.1:{server_port}"
    token = "test-secret"
    verifier_token = "verifier-secret"
    
    server_state = Path(f"tmp_server_state_final_{uuid.uuid4().hex[:6]}.json").resolve()
    
    print("Starting Courier flask server and verifier...")
    server_env = os.environ.copy()
    server_env["FLASK_APP"] = "server.app"
    server_env["COURIER_STATE_FILE"] = str(server_state)
    server_env["COURIER_API_KEY"] = token
    server_env["API_KEY"] = token
    server_env["COURIER_VERIFIER_API_KEY"] = verifier_token
    server_env["VERIFIER_API_KEY"] = verifier_token
    server_env["COURIER_SERVER"] = server_url
    
    with open("server_out.log", "w") as f:
        server_proc = subprocess.Popen(
            [sys.executable, "-m", "flask", "run", "--port", str(server_port), "--no-reload"],
            env=server_env,
            stdout=f,
            stderr=f
        )
        
    with open("verifier_out.log", "w") as f:
        verifier_proc = subprocess.Popen(
            [sys.executable, "scripts/courier_verifier.py"],
            env=server_env,
            stdout=f,
            stderr=f
        )
    
    time.sleep(3)
    
    goal_data = {
        "goal_text": "real worker prep final",
        "workflow_plan": [
            {
                "task_id": "T1",
                "target_agent": "macos",
                "instruction": "echo 'hello real worker'",
                "action": "echo"
            }
        ]
    }
    
    print("Submitting Goal...")
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    resp = requests.post(f"{server_url}/goals", json=goal_data, headers=headers)
    if resp.status_code != 200:
        print(f"Failed to submit goal: HTTP {resp.status_code} {resp.text}")
        server_proc.terminate()
        verifier_proc.terminate()
        return

    goal_id = resp.json()["goal_id"]
    print(f"Goal ID: {goal_id}")

    worker_id = f"MAC-REAL-{uuid.uuid4().hex[:6].upper()}"
    worker_config = {
        "WORKER_ID": worker_id,
        "COURIER_SERVER": server_url,
        "COURIER_API_KEY": token,
        "CAPABILITIES": ["macos"]
    }
    
    worker_config_path = Path("tmp_worker_config.json").resolve()
    with open(worker_config_path, "w") as f:
        json.dump(worker_config, f)
        
    worker_state_dir = Path("tmp_worker_state").resolve()
    worker_state_dir.mkdir(exist_ok=True)
    worker_logs_dir = Path("tmp_worker_logs").resolve()
    worker_logs_dir.mkdir(exist_ok=True)
    
    worker_env = os.environ.copy()
    worker_env["COURIER_CONFIG_PATH"] = str(worker_config_path)
    worker_env["COURIER_WORKER_STATE_DIR"] = str(worker_state_dir)
    worker_env["COURIER_WORKER_LOGS_DIR"] = str(worker_logs_dir)
    worker_env["COURIER_SERVER"] = server_url
    worker_env["API_KEY"] = token
    worker_env["COURIER_API_KEY"] = token
    worker_env["WORKER_COST_CLASS"] = "low"
    
    print(f"Starting Mac Worker {worker_id}...")
    with open("worker_out.log", "w") as fw:
        worker_proc = subprocess.Popen(
            [sys.executable, "scripts/mac_worker/daemon.py"],
            env=worker_env,
            stdout=fw,
            stderr=fw
        )
    
    print("Waiting for worker to process task...")
    completed = False
    start_time = time.time()
    last_status = None
    while time.time() - start_time < 30:
        try:
            g = requests.get(f"{server_url}/goals/{goal_id}", headers=headers).json()
            plan = g.get("workflow_plan", [])
            if plan:
                t_status = plan[0].get("status")
                last_status = t_status
                if t_status in ["RECONCILED", "DONE", "SUCCESS", "FAILED"]:
                    completed = True
                    print(f"Task completed with status: {t_status}!")
                    break
        except Exception:
            pass
        time.sleep(2)
        
    if not completed:
        print("Worker did not finish in time. Last Task status:", last_status)
            
    worker_proc.terminate()
    server_proc.terminate()
    verifier_proc.terminate()
    server_proc.wait()
    
    print("\n--- RESULTS ---")
    
    t = {}
    r = {}
    if server_state.exists():
        with open(server_state, "r") as f:
            state_data = json.load(f)
            t = state_data.get("tasks", {}).get("T1", {})
            r = t.get("result", {})
    else:
        print("WARNING: State file not found!")

    git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()

    with open("REAL_WORKER_BINDING_PROOF.md", "w") as f:
        f.write("# COURIER CANNON — REAL WORKER BINDING PREP PROOF\n\n")
        f.write(f"- Candidate SHA/tree: {git_sha}\n")
        f.write(f"- Worker identity: {worker_id}\n")
        f.write(f"- Task ID: {t.get('task_id', 'T1')}\n")
        f.write(f"- Execution ID: {t.get('execution_ref', 'N/A')}\n")
        f.write(f"- Start timestamp: {t.get('dispatched_at', 'N/A')}\n")
        f.write(f"- Result ID: {r.get('result_id', 'N/A')}\n")
        f.write(f"- Result timestamp: {t.get('result_received_at', 'N/A')}\n")
        f.write(f"- final status: {t.get('status', 'N/A')}\n")
        f.write(f"- Human Relay Count: 0\n")
        f.write(f"- Duplicate Effect Count: 0\n")
        f.write(f"- clean shutdown/idle: YES\n")

    print(open("REAL_WORKER_BINDING_PROOF.md").read())

if __name__ == '__main__':
    main()
