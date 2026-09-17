import os, sys, time, subprocess, json, threading
from unittest.mock import patch

# Monkeypatch sys.path to allow importing from scripts
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from scripts.windows_worker import daemon

def run_proof():
    print("Testing W25 EXACT PROCESS CLEANUP...")

    # We'll spawn a child process that sleeps for 60 seconds
    instruction = r'.venv_service\Scripts\python.exe -c "import time; time.sleep(60)"'

    
    # We monkeypatch communicate to timeout immediately
    original_communicate = subprocess.Popen.communicate
    def mock_communicate(self, input=None, timeout=None):
        if "powershell" in " ".join(self.args).lower():
            time.sleep(2) # Let the child spawn
            raise subprocess.TimeoutExpired(self.args, 1)
        return original_communicate(self, input=input, timeout=timeout)
        
    daemon.subprocess.Popen.communicate = mock_communicate

    task = {
        "task_id": "T-W25",
        "goal_id": "G-W25",
        "instruction": instruction,
        "target_agent": "windows",
        "attempt_id": "T-W25:attempt:1",
        "dispatch_id": "dispatch-1",
        "execution_ref": "exec-1",
        "worker_id": "w25-worker"
    }

    config = {"WORKER_ID": "w25-worker"}

    print("Running task...")
    res = daemon.run_task(task, config)
    
    daemon.subprocess.Popen.communicate = original_communicate

    print("Checking for leaked python processes...")
    try:
        # Check specifically for python.exe running this command
        out = subprocess.check_output('wmic process where "name=\'python.exe\' and commandline like \'%time.sleep(60)%\'" get processid', shell=True, text=True, errors='ignore')
        pids = [line.strip() for line in out.splitlines() if line.strip() and line.strip().isdigit()]
    except subprocess.CalledProcessError:
        # WMIC returns non-zero if no instances found, which means no leak.
        pids = []
    
    if pids:
        for pid in pids:
            subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
        sys.exit(f"W25 Proof Failed: Leaked processes detected: {pids}")

    print("PASS_W25: EXACT_PROCESS_CLEANUP")

if __name__ == "__main__":
    run_proof()
