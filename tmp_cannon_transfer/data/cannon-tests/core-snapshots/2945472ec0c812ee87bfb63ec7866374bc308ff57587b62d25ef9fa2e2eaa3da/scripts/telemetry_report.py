import json
import sys
import os

def generate_telemetry_report(state_path):
    if not os.path.exists(state_path):
        print("State file not found:", state_path)
        return

    with open(state_path, 'r') as f:
        try:
            state = json.load(f)
        except Exception as e:
            print("Failed to parse state file:", e)
            return

    goals = state.get("goals", {})
    tasks = state.get("tasks", {})
    workers = state.get("workers", {})

    total_goals = len(goals)
    completed_goals = sum(1 for g in goals.values() if g.get("status") == "DONE")
    
    total_tasks = len(tasks)
    total_attempts = sum(t.get("attempts", 0) for t in tasks.values())
    reconciled_tasks = sum(1 for t in tasks.values() if t.get("status") == "RECONCILED")
    
    active_workers = len(workers)
    
    print("=== COURIER COST & TELEMETRY REPORT ===")
    print(f"Goals Total: {total_goals}")
    print(f"Goals Completed: {completed_goals}")
    print(f"Tasks Total: {total_tasks}")
    print(f"Tasks Reconciled: {reconciled_tasks}")
    print(f"Worker Attempts Total: {total_attempts}")
    print(f"Workers Registered: {active_workers}")
    print("---------------------------------------")
    print("Note: Advanced token tracking/tool call data requires provider-side logs.")
    
if __name__ == '__main__':
    path = "server/state/central_state.json"
    generate_telemetry_report(path)
