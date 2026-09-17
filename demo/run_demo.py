import os
import sys
import time
import subprocess
import requests
import json
import uuid

SERVER_URL = "http://192.168.178.87:8080"
API_KEY = "win-central-secret"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_step(title, msg, color=CYAN):
    print(f"\n{color}{BOLD}=== {title} ==={RESET}")
    print(f"{msg}\n")

def submit_goal():
    uid = uuid.uuid4().hex[:6]
    t1 = f"t1-{uid}"
    t2 = f"t2-{uid}"
    t3 = f"t3-{uid}"
    goal = {
        "goal_text": "Demo: Market Research Pipeline",
        "workflow_plan": [
            {"task_id": t1, "target_agent": "mac", "instruction": "echo Extracting data", "mode": "NATIVE"},
            {"task_id": t2, "target_agent": "windows", "instruction": "echo Processing on GPU", "mode": "NATIVE", "depends_on": [t1]},
            {"task_id": t3, "target_agent": "windows", "instruction": "echo Generating report", "mode": "NATIVE", "depends_on": [t2]}
        ]
    }
    resp = requests.post(f"{SERVER_URL}/goals", json=goal, headers=HEADERS)
    resp.raise_for_status()
    return resp.json().get("goal_id"), t1, t2, t3

def get_goal_state(goal_id):
    resp = requests.get(f"{SERVER_URL}/goals/{goal_id}", headers=HEADERS)
    if resp.status_code == 200:
        return resp.json()
    return None

def start_mac_worker():
    return subprocess.Popen(
        ["python3", "scripts/mac_worker/daemon.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        preexec_fn=os.setsid
    )

def start_windows_worker():
    return subprocess.Popen(
        ["ssh", "windows-ai", "cd C:\\Users\\lol\\2026-workspace\\2026-courier\\scripts\\windows_worker && start.bat"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        preexec_fn=os.setsid
    )

def main():
    print(f"\n{BOLD}Courier - Zero-Touch Handoff Demo{RESET}\n")
    
    print_step("1. GOAL RECEIVED", f"Submitting multi-platform goal: Market Research Pipeline", BLUE)
    goal_id, t1, t2, t3 = submit_goal()
    print(f" {GREEN}-> Goal assigned ID: {goal_id}{RESET}")
    
    print_step("2. MOTOR RUNNING", "Goal is now durable. The OS-owned Motor takes over.", BLUE)
    
    print(f" {YELLOW}-> Starting Worker 1 (Mac){RESET}")
    mac_proc = start_mac_worker()
    win_proc = None
    
    task1_done = False
    task2_picked_up = False
    
    try:
        while True:
            state = get_goal_state(goal_id)
            if not state:
                time.sleep(1)
                continue
                
            status = state.get("goal", {}).get("status") if "goal" in state else state.get("status")
            
            if "goal" in state:
                tasks = {t["task_id"]: t.get("status", "QUEUED") for t in state.get("tasks", [])}
                tasks.update({t["task_id"]: t.get("status", "QUEUED") for t in state.get("goal", {}).get("workflow_plan", [])})
            else:
                tasks = {t["task_id"]: t.get("status", "QUEUED") for t in state.get("workflow_plan", [])}
            
            t1_status = tasks.get(t1)
            t2_status = tasks.get(t2)
            
            if not task1_done and t1_status == "RECONCILED":
                print_step("3. TASK 1 COMPLETE", "Mac Worker finished data extraction.", GREEN)
                print(f" {RED}-> SIMULATING CRASH: Killing Worker 1 (Mac){RESET}")
                os.killpg(os.getpgid(mac_proc.pid), 9)
                mac_proc.wait()
                task1_done = True
                
                print_step("4. LEDGER RECOVERED", "Motor preserves state. Task 2 is READY but waiting for heavy compute.", YELLOW)
                time.sleep(3)
                
                print_step("5. HANDOFF / WORKER REPLACED", "Starting Worker 2 (Windows GPU node) to resume work...", CYAN)
                win_proc = start_windows_worker()
                
            if task1_done and not task2_picked_up and t2_status in ["DISPATCHED", "RESULT_RECEIVED", "RECONCILED"]:
                print(f" {GREEN}-> Worker 2 (Windows) successfully picked up Task 2!{RESET}")
                task2_picked_up = True
                
            if status == "DONE":
                print_step("6. VERIFIED RESULT", "All tasks complete. Final result is verified.", GREEN)
                print_step("7. DONE", f"Goal {goal_id} achieved gracefully across multiple workers despite interruption.", BOLD)
                break
                
            time.sleep(1.5)
    finally:
        if mac_proc and mac_proc.poll() is None:
            os.killpg(os.getpgid(mac_proc.pid), 9)
        if win_proc and win_proc.poll() is None:
            os.killpg(os.getpgid(win_proc.pid), 9)
            subprocess.run(["ssh", "windows-ai", "powershell -Command \"Stop-Process -Name python -Force\""], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

if __name__ == "__main__":
    main()
