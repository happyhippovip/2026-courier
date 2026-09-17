import os
import sys
import time
import subprocess
import requests
import json
import uuid
import socket
import argparse

os.environ["COURIER_SERVER"] = "http://127.0.0.1:8080"
os.environ["COURIER_WORKER_API_KEY"] = "demo-secret"
os.environ["COURIER_VERIFIER_API_KEY"] = "demo-verifier-secret"
os.environ["COURIER_API_KEY"] = "demo-secret"
os.environ["PYTHONPATH"] = os.getcwd()

SERVER_URL = "http://127.0.0.1:8080"
API_KEY = "demo-secret"
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

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def submit_goal():
    uid = uuid.uuid4().hex[:6]
    t1 = f"t1-{uid}"
    t2 = f"t2-{uid}"
    t3 = f"t3-{uid}"
    goal = {
        "goal_text": "Demo: Market Research Pipeline",
        "workflow_plan": [
            {"task_id": t1, "target_agent": "mac", "instruction": "echo Extracting market data", "mode": "NATIVE"},
            {"task_id": t2, "target_agent": "mac", "instruction": "echo Processing metrics", "mode": "NATIVE", "depends_on": [t1]},
            {"task_id": t3, "target_agent": "mac", "instruction": "echo Generating final report", "mode": "NATIVE", "depends_on": [t2]}
        ]
    }
    for _ in range(5):
        try:
            resp = requests.post(f"{SERVER_URL}/goals", json=goal, headers=HEADERS)
            resp.raise_for_status()
            return resp.json().get("goal_id"), t1, t2, t3
        except requests.exceptions.ConnectionError:
            time.sleep(1)
    raise Exception("Could not connect to local Motor server")

def get_goal_state(goal_id):
    try:
        resp = requests.get(f"{SERVER_URL}/goals/{goal_id}", headers=HEADERS)
        if resp.status_code == 200:
            return resp.json()
    except requests.exceptions.ConnectionError:
        pass
    return None

def start_server():
    env = os.environ.copy()
    env["COURIER_STATE_FILE"] = "server/state/demo_state.json"
    return subprocess.Popen(
        [sys.executable, "-m", "server.app"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env
    )

def start_verifier():
    return subprocess.Popen(
        [sys.executable, "scripts/courier_verifier.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=os.environ
    )

def start_worker(name_suffix="1"):
    env = os.environ.copy()
    env["WORKER_ID_OVERRIDE"] = f"DEMO-WORKER-{name_suffix}"
    return subprocess.Popen(
        [sys.executable, "scripts/mac_worker/daemon.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env
    )

def run_autonomy_test():
    print(f"\n{BOLD}Courier - Headless Autonomy Test{RESET}\n")
    print("This mode proves that Motor and Workers progress independently of UI polling.")
    
    server_proc = start_server()
    verifier_proc = start_verifier()
    mac_proc = None
    win_proc = None
    
    try:
        goal_id, t1, t2, t3 = submit_goal()
        print(f"Goal {goal_id} submitted.")
        
        mac_proc = start_worker("A")
        print("Worker A started. Sleeping 6 seconds (no polling)...")
        time.sleep(6)
        
        print("Simulating crash by killing Worker A...")
        mac_proc.terminate()
        mac_proc.wait()
        
        print("Worker B started. Sleeping 15 seconds (no polling)...")
        win_proc = start_worker("B")
        time.sleep(15)
        
        state = get_goal_state(goal_id)
        status = state.get("goal", {}).get("status") if state and "goal" in state else state.get("status") if state else "UNKNOWN"
        
        if status == "DONE":
            print(f"{GREEN}SUCCESS: Goal reached DONE autonomously without UI control flow!{RESET}")
            sys.exit(0)
        else:
            print(f"{RED}FAIL: Goal ended in status: {status}{RESET}")
            sys.exit(1)
            
    finally:
        for p in [server_proc, verifier_proc, mac_proc, win_proc]:
            if p and p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    p.kill()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--autonomy-test", action="store_true", help="Run without polling to prove autonomous Motor behavior")
    args = parser.parse_args()

    if is_port_in_use(8080):
        print(f"{RED}Error: Port 8080 is already in use. Please stop any existing Courier server before running the local demo.{RESET}")
        sys.exit(1)

    if os.path.exists("server/state/demo_state.json"):
        os.remove("server/state/demo_state.json")

    if args.autonomy_test:
        run_autonomy_test()
        return

    print(f"\n{BOLD}Courier - Standalone Local Demo{RESET}\n")
    print_step("0. BOOTSTRAPPING", "Starting local Motor and Verifier services...", BLUE)
    server_proc = start_server()
    verifier_proc = start_verifier()
    
    mac_proc = None
    win_proc = None
    
    try:
        print_step("1. GOAL RECEIVED", f"Submitting multi-step goal: Market Research Pipeline", BLUE)
        goal_id, t1, t2, t3 = submit_goal()
        print(f" {GREEN}-> Goal assigned ID: {goal_id}{RESET}")
        
        print_step("2. MOTOR RUNNING", "Goal is now durable. The Motor takes over.", BLUE)
        
        print(f" {YELLOW}-> Starting Local Worker Process A...{RESET}")
        mac_proc = start_worker("A")
        
        task1_done = False
        task2_picked_up = False
        
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
                print_step("3. TASK 1 COMPLETE", "Worker A finished data extraction.", GREEN)
                print(f" {RED}-> SIMULATING CRASH: Terminating Local Worker Process A...{RESET}")
                mac_proc.terminate()
                mac_proc.wait()
                task1_done = True
                
                print_step("4. STATE PRESERVED", "Motor preserves state. Task 2 is READY but waiting for a worker.", YELLOW)
                time.sleep(3)
                
                print_step("5. HANDOFF / WORKER REPLACED", "Starting Local Worker Process B to resume work...", CYAN)
                win_proc = start_worker("B")
                
            if task1_done and not task2_picked_up and t2_status in ["DISPATCHED", "RESULT_RECEIVED", "RECONCILED"]:
                print(f" {GREEN}-> Worker B successfully picked up Task 2!{RESET}")
                task2_picked_up = True
                
            if status == "DONE":
                print_step("6. VERIFIED RESULT", "All tasks complete. Final result is verified.", GREEN)
                print_step("7. DONE", f"Goal {goal_id} achieved gracefully across replaceable workers despite interruption.", BOLD)
                break
                
            time.sleep(1.5)
    except KeyboardInterrupt:
        print("\nDemo interrupted.")
    finally:
        print(f" {YELLOW}-> Cleaning up processes...{RESET}")
        for p in [server_proc, verifier_proc, mac_proc, win_proc]:
            if p and p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    p.kill()

if __name__ == "__main__":
    main()
