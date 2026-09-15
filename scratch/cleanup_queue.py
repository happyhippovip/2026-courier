import sys
import json
from pathlib import Path

queue_dir = Path("events/opportunity-queue")
active_tasks = []
ready_tasks = []
stale_tasks = []

# Collect and categorize tasks
for f in queue_dir.glob("*.json"):
    try:
        with open(f, "r") as file:
            data = json.load(file)
            
        status = data.get("status")
        opp_id = data.get("opportunity_id")
        
        if status == "ACTIVE":
            active_tasks.append((f, data))
        elif status == "READY":
            ready_tasks.append((f, data))
    except Exception as e:
        print(f"Error reading {f}: {e}")

print(f"Found {len(active_tasks)} ACTIVE, {len(ready_tasks)} READY tasks.")

# Enforce ACTIVE <= 1 per writer scope (we'll just enforce globally for now)
if len(active_tasks) > 1:
    print(f"Too many ACTIVE tasks ({len(active_tasks)}). Demoting all but the highest priority to STALE.")
    active_tasks.sort(key=lambda x: x[1].get("priority", 0), reverse=True)
    for f, data in active_tasks[1:]:
        data["status"] = "STALE"
        with open(f, "w") as file:
            json.dump(data, file, indent=2)

# Enforce READY <= 5
if len(ready_tasks) > 5:
    print(f"Too many READY tasks ({len(ready_tasks)}). Demoting all but the top 5 highest priority to INVALID.")
    ready_tasks.sort(key=lambda x: x[1].get("priority", 0), reverse=True)
    for f, data in ready_tasks[5:]:
        data["status"] = "INVALID"
        with open(f, "w") as file:
            json.dump(data, file, indent=2)

print("Cleanup complete.")
