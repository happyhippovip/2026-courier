#!/usr/bin/env python3
import json
import os
import datetime

def export_customer_data(export_path="customer_export.json"):
    """
    Exports customer-owned durable data (goals, results, artifact refs, timestamps)
    without exporting secrets, chain-of-thought, or internal prompt engineering.
    """
    # Assuming central_state.json holds the state
    state_file = 'central_state.json'
    if not os.path.exists(state_file):
        print(f"No state file found at {state_file}.")
        return

    with open(state_file, 'r') as f:
        try:
            state = json.load(f)
        except json.JSONDecodeError:
            print("Failed to decode state file.")
            return

    export_data = {
        "exported_at": datetime.datetime.utcnow().isoformat() + "Z",
        "goals": [],
        "tasks": []
    }

    # Extract goals (if any in state)
    if "goals" in state:
        for goal_id, goal_data in state["goals"].items():
            export_data["goals"].append({
                "goal_id": goal_id,
                "description": goal_data.get("description", ""),
                "status": goal_data.get("status", "UNKNOWN"),
                "created_at": goal_data.get("created_at", ""),
                "completed_at": goal_data.get("completed_at", "")
            })

    # Extract tasks
    if "tasks" in state:
        for task_id, task_data in state["tasks"].items():
            # Exclude chain of thought, full logs, secrets
            export_data["tasks"].append({
                "task_id": task_id,
                "type": task_data.get("type", "UNKNOWN"),
                "status": task_data.get("status", "UNKNOWN"),
                "created_at": task_data.get("created_at", ""),
                "completed_at": task_data.get("completed_at", ""),
                "artifacts": task_data.get("artifacts", []),
                "error_summary": task_data.get("error_summary", "")
            })
            
    with open(export_path, 'w') as f:
        json.dump(export_data, f, indent=2)

    print(f"Customer data successfully exported to {export_path}")

if __name__ == "__main__":
    import sys
    export_path = sys.argv[1] if len(sys.argv) > 1 else "customer_export.json"
    export_customer_data(export_path)
