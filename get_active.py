import json

with open("server/state/central_state.json", "r") as f:
    state = json.load(f)

for tid, t in state.get("tasks", {}).items():
    if t.get("status") not in ["RECONCILED", "FAILED_TERMINAL", "HUMAN_REQUIRED"]:
        print(json.dumps(t, indent=2))
