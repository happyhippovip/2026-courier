import json, os

with open("server/state/central_state.json", "r") as f:
    state = json.load(f)
    
for goal in state.get("goals", {}).values():
    if goal.get("status") == "ACTIVE":
        goal["status"] = "BLOCKED"

# Free workers
for w in state.get("workers", {}).values():
    w["current_task"] = None
    w["available"] = True
    
# Save back atomically
import tempfile
fd, path = tempfile.mkstemp()
with os.fdopen(fd, 'w') as f:
    json.dump(state, f, indent=2)
os.replace(path, "server/state/central_state.json")

