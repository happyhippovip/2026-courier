#!/usr/bin/env python3
import json
import os
import subprocess
import time
import uuid
import psutil

class WindowsPrimaryWorker:
    def exit_gracefully(self):
        if os.path.exists(self.lock_file):
            os.remove(self.lock_file)
    def __init__(self, worker_id="WIN_PRIMARY_01"):
        self.worker_id = worker_id
        self.capabilities = ["local_windows", "python", "powershell", "file_system"]
        self.cost_class = "CHEAP"
        self.state_file = 'worker_state.json'
        self.config_file = 'worker_profile.json'
        self.current_task = None
        self.owned_pids = set()
        self.profile = "LOW_RESOURCE"
        self.load_profile()
        # Ensure single instance lock
        self.lock_file = 'worker.lock'
        if os.path.exists(self.lock_file):
            print("Duplicate worker detected. Exiting.")
            sys.exit(1)
        open(self.lock_file, 'w').close()
        
    def load_profile(self):
        # Default fallback is LOW_RESOURCE
        self.profile = "LOW_RESOURCE"
        self.max_concurrency = 1
        self.cpu_limit = 85.0
        self.mem_limit = 85.0
        self.poll_interval = 5.0
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    conf = json.load(f)
                    profile = conf.get("profile", "LOW_RESOURCE")
                    if profile == "STANDARD":
                        self.max_concurrency = 4
                        self.cpu_limit = 90.0
                        self.mem_limit = 90.0
                        self.poll_interval = 2.0
                        self.profile = "STANDARD"
                    elif profile == "HIGH_CAPACITY":
                        self.max_concurrency = 16
                        self.cpu_limit = 95.0
                        self.mem_limit = 95.0
                        self.poll_interval = 0.5
                        self.profile = "HIGH_CAPACITY"
            except Exception:
                pass

    def register(self):
        print(f"Registering worker {self.worker_id} with profile {self.profile}")
        
    def load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    self.current_task = state.get("current_task")
                    self.owned_pids = set(state.get("owned_pids", []))
                    if self.current_task:
                        print("Recovered task from previous run (Reboot Recovery).")
            except Exception:
                pass

    def save_state(self):
        with open(self.state_file, 'w') as f:
            json.dump({
                "current_task": self.current_task,
                "owned_pids": list(self.owned_pids)
            }, f)

    def is_resource_saturated(self):
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory().percent
        if cpu > self.cpu_limit or mem > self.mem_limit:
            print(f"[RESOURCE PRESSURE] CPU: {cpu}%, Mem: {mem}%. Limits -> CPU: {self.cpu_limit}%, Mem: {self.mem_limit}%")
            return True
        return False

    def claim_task(self, task):
        if self.current_task is not None:
            print("Already processing a task (single-flight enforced).")
            return False
            
        if self.is_resource_saturated():
            print("Local machine is saturated. Rejecting claim. Triggering HOSTED_FALLBACK.")
            return False
            
        self.current_task = {
            "task_id": task["task_id"],
            "attempt_id": task.get("attempt_id", 1),
            "dispatch_id": str(uuid.uuid4()),
            "execution_ref": f"exec_{self.worker_id}_{task['task_id']}"
        }
        self.save_state()
        print(f"Claimed task: {self.current_task['task_id']}")
        return True

    def execute_bounded(self, cmd, timeout=300):
        if not self.current_task:
            return
            
        print(f"Executing: {cmd} with execution_ref {self.current_task['execution_ref']}")
        proc = subprocess.Popen(cmd, shell=True)
        self.owned_pids.add(proc.pid)
        self.save_state()
        
        try:
            proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            print("Timeout reached.")
        
        self.cleanup("DONE" if proc.returncode == 0 else "FAILED_TERMINAL")

    def cleanup(self, terminal_state):
        if not self.current_task:
            return
            
        print(f"Terminal outcome: {terminal_state}. Cleaning up owned processes...")
        for pid in list(self.owned_pids):
            try:
                p = psutil.Process(pid)
                for child in p.children(recursive=True):
                    child.terminate()
                p.terminate()
            except psutil.NoSuchProcess:
                pass
            except Exception as e:
                print(f"Error terminating PID {pid}: {e}")
                
        self.owned_pids.clear()
        self.current_task = None
        self.save_state()
        print("Cleanup complete. Clean idle reached.")

    def idle_poll(self):
        # Sleeping backoff idle polling
        print(f"Polling with {self.poll_interval}s backoff to avoid hot idle loop...")
        time.sleep(self.poll_interval)

if __name__ == '__main__':
    worker = WindowsPrimaryWorker()
    worker.register()
    worker.load_state()
    # Simulated resource check
    saturated = worker.is_resource_saturated()
    if not saturated:
        worker.claim_task({"task_id": "T-100"})
    else:
        print("Fallback required.")
    worker.idle_poll()


