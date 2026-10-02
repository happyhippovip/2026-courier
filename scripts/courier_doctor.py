#!/usr/bin/env python3
"""
Courier Doctor: Beginner UX tool to diagnose the health of the local Courier Symphony system.
"""

import json
import os
import urllib.request
import urllib.error
from pathlib import Path
import time

def check_ledger():
    ledger_path = Path("server/state/central_state.json")
    if not ledger_path.exists():
        return False, f"Missing {ledger_path}"
    try:
        with open(ledger_path, "r") as f:
            state = json.load(f)
        goals = len(state.get("goals", {}))
        workers = len(state.get("workers", {}))
        return True, f"Valid JSON. Goals: {goals}, Known Workers: {workers}"
    except Exception as e:
        return False, f"Corrupt JSON: {e}"

def check_server():
    try:
        req = urllib.request.Request("http://127.0.0.1:8080/goals")
        # Just check if it responds, we might get 401 Unauthorized but that means the server is UP
        with urllib.request.urlopen(req, timeout=2) as response:
            pass
        return True, "Server responding on port 8080"
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return True, "Server responding (Auth required)"
        return True, f"Server responding ({e.code})"
    except Exception as e:
        return False, f"Server unreachable: {e}"

def check_stuck_tasks():
    ledger_path = Path("server/state/central_state.json")
    if not ledger_path.exists():
        return True, "No ledger to check"
    try:
        with open(ledger_path, "r") as f:
            state = json.load(f)
        
        stuck_tasks = []
        now = time.time()
        for t_id, task in state.get("tasks", {}).items():
            if task.get("status") == "DISPATCHED":
                w_id = task.get("worker_id")
                worker = state.get("workers", {}).get(w_id, {})
                last_seen = worker.get("last_seen", 0)
                if now - last_seen > 300: # 5 minutes
                    stuck_tasks.append(t_id)
        if stuck_tasks:
            return False, f"Found {len(stuck_tasks)} stuck tasks waiting on dead workers: {', '.join(stuck_tasks)}"
        return True, "All dispatched tasks have active workers."
    except Exception:
        return True, "Could not check tasks"

def run_diagnostics():
    print("=== Courier Symphony Doctor ===")
    checks = [
        ("Ledger State", check_ledger),
        ("Server Health", check_server),
        ("Task Health", check_stuck_tasks)
    ]
    
    all_pass = True
    for name, func in checks:
        print(f"Checking {name}...", end=" ")
        passed, msg = func()
        if passed:
            print(f"[\033[92mOK\033[0m] - {msg}")
        else:
            print(f"[\033[91mFAIL\033[0m] - {msg}")
            all_pass = False
            
    print("===============================")
    if all_pass:
        print("System is healthy. You are good to go!")
    else:
        print("Issues detected. Please resolve the above failures.")

if __name__ == "__main__":
    run_diagnostics()
