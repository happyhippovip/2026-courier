#!/usr/bin/env python3
import time
import requests
import os
import sys
import json
from pathlib import Path

# Add local path to import integration contract
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from integration_contract import verify_safety
except ImportError:
    print("Warning: integration_contract not found, using dummy safety check.")
    def verify_safety(cost, inv, tasks): return True, "Safe"

API_URL = os.environ.get("COURIER_SERVER", "http://127.0.0.1:8080").rstrip("/")
API_KEY = os.environ.get("COURIER_API_KEY", "")
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# E.g. $0.02 per standard complex task completion, or per API call depending on metric
COST_PER_INVOCATION = 0.01

def fetch_metrics():
    try:
        resp = requests.get(f"{API_URL}/system/metrics", headers=HEADERS, timeout=5)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        pass
    return None

def halt_system(reason):
    print(f"HALTING SYSTEM: {reason}")
    try:
        resp = requests.post(f"{API_URL}/system/halt", json={"reason": reason}, headers=HEADERS, timeout=5)
        if resp.status_code == 200:
            print("System successfully halted at control plane.")
        else:
            print(f"Failed to halt system: {resp.text}")
    except Exception as e:
        print(f"Failed to issue halt to API: {e}")

def get_bodyguard_invocations():
    total_invocations = 0
    states_dir = Path("events/agent-states")
    if not states_dir.exists():
        return 0
    for state_file in states_dir.glob("*.json"):
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
            total_invocations += data.get("model_calls_incurred", 0)
        except Exception:
            pass
    return total_invocations

def main():
    print("Starting Courier Progress Beacon and Value Accountant...")
    while True:
        metrics = fetch_metrics()
        if metrics:
            if metrics.get("system_halted"):
                print(f"[BEACON] SYSTEM IS HALTED. Reason: {metrics.get('halt_reason')}")
            else:
                invocations = get_bodyguard_invocations()
                cost = invocations * COST_PER_INVOCATION
                active_tasks = metrics.get("active_tasks", 0)
                
                print(f"[BEACON] Cost: ${cost:.2f} | Invocations: {invocations} | Active Tasks: {active_tasks}")
                
                safe, reason = verify_safety(cost, invocations, active_tasks)
                if not safe:
                    halt_system(reason)
        else:
            print("[BEACON] Failed to fetch metrics from Courier server.")
            
        time.sleep(5)

if __name__ == "__main__":
    main()
