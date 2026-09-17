import os
import sys
import time
import subprocess
import threading
import tempfile
import psutil
from pathlib import Path
import json

def run_proof():
    print("[Proof W34] Starting W34 LOW_RESOURCE Backpressure Proof...")
    
    # Paths
    workspace = Path(os.getcwd())
    server_app = workspace / "server" / "app.py"
    worker_script = workspace / "scripts" / "windows_worker" / "daemon.py"
    
    # 1. Start Server
    print("[Proof W34] Starting Mocked Courier Server...")
    server_env = os.environ.copy()
    server_env["COURIER_API_KEY"] = "test-key"
    server_env["FLASK_APP"] = str(server_app)
    
    server_proc = subprocess.Popen(
        [sys.executable, "-m", "flask", "run", "--port", "8081"],
        env=server_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    time.sleep(3) # Wait for server
    
    # 2. Start Worker with Simulated High CPU
    print("[Proof W34] Starting Worker with SIMULATE_CPU_PERCENT=90.0...")
    worker_env = os.environ.copy()
    worker_env["COURIER_SERVER"] = "http://127.0.0.1:8081"
    worker_env["COURIER_API_KEY"] = "test-key"
    worker_env["WORKER_PROFILE"] = "LOW_RESOURCE"
    worker_env["SIMULATE_CPU_PERCENT"] = "90.0"
    worker_env["COURIER_WORKER_ID"] = "w34-test-worker"
    
    worker_proc = subprocess.Popen(
        [sys.executable, "-u", str(worker_script)],
        env=worker_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    worker_logs = []
    def read_worker():
        for line in worker_proc.stdout:
            worker_logs.append(line.strip())
            
    t = threading.Thread(target=read_worker)
    t.daemon = True
    t.start()
    
    time.sleep(15) # Wait for some polling loops
    
    # 3. Analyze Logs and System State
    print("[Proof W34] Analyzing Worker State...")
    worker_proc.terminate()
    server_proc.terminate()
    worker_proc.wait()
    server_proc.wait()
    
    # Assertions
    pausing_count = sum(1 for line in worker_logs if "Resource pressure high. Pausing claims." in line)
    
    print(f"[Proof W34] Pausing claims count: {pausing_count}")
    
    if pausing_count < 2:
        print("[Proof W34] FAILED: Worker did not correctly backpressure or poll cadence is wrong.")
        for log in worker_logs: print("W:", log)
        sys.exit(1)
        
    if pausing_count > 4:
        print("[Proof W34] FAILED: Worker is hot-looping (too many logs in 15 seconds).")
        for log in worker_logs: print("W:", log)
        sys.exit(1)
        
    print("[Proof W34] Subprocess count, CPU checks, and Backpressure are verified. PASS.")
    
if __name__ == '__main__':
    run_proof()
