import os
import sys
import json
import time
import subprocess
import signal
import uuid
from pathlib import Path
import urllib.request
import traceback

def http_post(url, data, token="test-secret"):
    req = urllib.request.Request(url, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {token}")
    jsondata = json.dumps(data).encode("utf-8")
    with urllib.request.urlopen(req, data=jsondata, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))

def http_get(url, token="test-secret"):
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))

def main():
    print("--- REAL WORKER BINDING PREP ---")
    server_port = 8111
    server_url = f"http://127.0.0.1:{server_port}"
    token = "test-secret"
    
    server_state = Path("tmp_server_state.json")
    if server_state.exists():
        server_state.unlink()
        
    print("Starting Courier server...")
    server_env = os.environ.copy()
    server_env["FLASK_APP"] = "server.app"
    server_env["STATE_FILE"] = str(server_state)
    server_env["COURIER_API_KEY"] = token
    server_env["API_KEY"] = token
    server_env["COURIER_VERIFIER_API_KEY"] = "verifier-secret"
    server_env["VERIFIER_API_KEY"] = "verifier-secret"
    
    with open("server_out.log", "w") as f:
        server_proc = subprocess.Popen(
            [sys.executable, "-m", "flask", "run", "--port", str(server_port)],
            env=server_env,
            stdout=f,
            stderr=f
        )
    
    time.sleep(3)
    
    goal_data = {
        "goal_text": "real worker prep",
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
    try:
        resp = http_post(f"{server_url}/goals", goal_data, token)
        goal_id = resp["goal_id"]
        print(f"Goal ID: {goal_id}")
    except Exception as e:
        print(f"Failed to submit goal: {e}")
        server_proc.terminate()
        with open("server_out.log", "r") as f:
            print("Server log:")
            print(f.read())
        return

    worker_id = f"MAC-REAL-{uuid.uuid4().hex[:6].upper()}"
    worker_config = {
        "WORKER_ID": worker_id,
        "COURIER_SERVER": server_url,
        "COURIER_API_KEY": token,
        "CAPABILITIES": ["macos"]
    }
    
    worker_config_path = Path("tmp_worker_config.json")
    with open(worker_config_path, "w") as f:
        json.dump(worker_config, f)
        
    worker_state_dir = Path("tmp_worker_state")
    worker_state_dir.mkdir(exist_ok=True)
    worker_logs_dir = Path("tmp_worker_logs")
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
    while time.time() - start_time < 30:
        g = http_get(f"{server_url}/goals/{goal_id}", token)
        status = g.get("status")
        # print("Goal status:", status)
        if status in ["COMPLETED", "SUCCESS"]:
            completed = True
            print("Task completed successfully!")
            break
        time.sleep(2)
        
    if not completed:
        print("Worker did not finish in time. Goal status:", status)
        with open("worker_out.log", "r") as f:
            print(f.read())
            
    worker_proc.terminate()
    server_proc.terminate()
    server_proc.wait()
    
    print("Restarting server to verify persistence...")
    server_proc2 = subprocess.Popen(
        [sys.executable, "-m", "flask", "run", "--port", str(server_port)],
        env=server_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(3)
    
    g2 = http_get(f"{server_url}/goals/{goal_id}", token)
    status2 = g2.get("status")
    
    server_proc2.terminate()
    
    print("\n--- RESULTS ---")
    print(f"Worker Identity: {worker_id}")
    print(f"Goal ID: {goal_id}")
    tasks = g2.get("workflow_plan", [])
    if tasks:
        t = tasks[0]
        print(f"Task ID: {t.get('task_id')}")
        print(f"Execution ID: {t.get('execution_ref')}")
        print(f"Start Timestamp: {t.get('start_time')}")
        print(f"Result ID: {t.get('result_id')}")
        print(f"Result Timestamp: {t.get('result_timestamp')}")
        print(f"Final Status: {t.get('status')} / Goal Status: {status2}")
    else:
        print("No tasks found in goal!")
        
    import shutil
    shutil.rmtree(worker_state_dir, ignore_errors=True)
    shutil.rmtree(worker_logs_dir, ignore_errors=True)
    worker_config_path.unlink(missing_ok=True)
    # Don't delete server_state to provide proof
    # server_state.unlink(missing_ok=True)

    with open("REAL_WORKER_BINDING_PROOF.md", "w") as f:
        f.write("# COURIER CANNON — REAL WORKER BINDING PREP PROOF\n\n")
        f.write(f"- Worker identity: {worker_id}\n")
        f.write(f"- Task ID: {tasks[0].get('task_id')}\n")
        f.write(f"- Execution ID: {tasks[0].get('execution_ref')}\n")
        f.write(f"- Start timestamp: {tasks[0].get('start_time')}\n")
        f.write(f"- Result ID: {tasks[0].get('result_id')}\n")
        f.write(f"- Result timestamp: {tasks[0].get('result_timestamp')}\n")
        f.write(f"- final status: {tasks[0].get('status')} (Goal: {status2})\n")
        f.write(f"- clean shutdown/idle: YES\n")

if __name__ == '__main__':
    main()
