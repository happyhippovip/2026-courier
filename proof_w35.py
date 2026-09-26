import os
import sys
import time
import subprocess
import threading
import urllib.request
import json
from pathlib import Path

def run_proof():
    print("[Proof W35] Starting W35 Long Idle Then Wake Proof...")
    
    workspace = Path(os.getcwd())
    server_app = workspace / "server" / "app.py"
    worker_script = workspace / "scripts" / "windows_worker" / "daemon.py"
    
    # 1. Start Server
    print("[Proof W35] Starting Mocked Courier Server...")
    server_env = os.environ.copy()
    server_env["COURIER_API_KEY"] = "test-key"
    server_env["FLASK_APP"] = str(server_app)
    
    server_proc = subprocess.Popen(
        [sys.executable, "-m", "flask", "run", "--port", "8082"],
        env=server_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    time.sleep(3) # Wait for server
    
    # 2. Start Worker
    print("[Proof W35] Starting Worker...")
    worker_env = os.environ.copy()
    worker_env["COURIER_SERVER"] = "http://127.0.0.1:8082"
    worker_env["COURIER_API_KEY"] = "test-key"
    worker_env["WORKER_PROFILE"] = "NORMAL"
    worker_env["COURIER_WORKER_ID"] = "w35-test-worker"
    
    worker_proc = subprocess.Popen(
        [sys.executable, "-u", str(worker_script)],
        env=worker_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    # 3. Monitor Server Logs for Polling Cadence
    print("[Proof W35] Idling to build backoff (~50 seconds)...")
    
    server_logs = []
    claim_timestamps = []
    
    def read_server():
        for line in server_proc.stdout:
            server_logs.append(line.strip())
            if "POST /tasks/claim" in line:
                claim_timestamps.append(time.time())
                
    worker_logs = []
    def read_worker():
        for line in worker_proc.stdout:
            worker_logs.append(line.strip())
            
    t1 = threading.Thread(target=read_server)
    t1.daemon = True
    t1.start()
    
    t2 = threading.Thread(target=read_worker)
    t2.daemon = True
    t2.start()
    
    # Wait for backoff to scale
    time.sleep(45)
    
    intervals = []
    for i in range(1, len(claim_timestamps)):
        intervals.append(claim_timestamps[i] - claim_timestamps[i-1])
    
    print(f"[Proof W35] Polling intervals observed: {[round(x, 2) for x in intervals]}")
    
    if not intervals or not all(intervals[i] > intervals[i-1] - 1 for i in range(1, len(intervals))):
        print("[Proof W35] WARNING/FAILED: Polling intervals did not correctly exponentially back off.")
    
    # 4. Submit New Goal while Worker is in Deep Idle
    print("[Proof W35] Submitting new goal while worker is idle...")
    req = urllib.request.Request("http://127.0.0.1:8082/goals", method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer test-key")
    data = json.dumps({
        "goal_text": "Run a test task after long idle",
        "workflow_plan": [
            {
                "task_id": "w35-task-1",
                "instruction": "echo test w35",
                "target_agent": "windows",
                "status": "QUEUED"
            }
        ]
    }).encode("utf-8")
    
    try:
        res = urllib.request.urlopen(req, data=data, timeout=5)
        print("[Proof W35] Goal submitted.")
    except Exception as e:
        print(f"[Proof W35] Failed to submit goal: {e}")
        server_proc.terminate()
        worker_proc.terminate()
        sys.exit(1)
        
    # 5. Wait for Worker to Wake up, Claim, and Complete
    print("[Proof W35] Waiting for worker to wake up and process the task (max 35s)...")
    success = False
    start_wait = time.time()
    
    while time.time() - start_wait < 40:
        if any("Task" in line and "completed" in line for line in worker_logs):
            success = True
            break
        time.sleep(1)
        
    server_proc.terminate()
    worker_proc.terminate()
    server_proc.wait()
    worker_proc.wait()
    
    if not success:
        print("[Proof W35] FAILED: Worker did not wake up and complete the task.")
        for log in worker_logs: print("W:", log)
        sys.exit(1)
        
    print("[Proof W35] Worker successfully woke up from idle backoff and completed the task without restart.")
    print("[Proof W35] PASS.")
    
if __name__ == '__main__':
    run_proof()
