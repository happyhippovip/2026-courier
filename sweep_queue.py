import json

with open("server/state/central_state.json", "r") as f:
    state = json.load(f)

for tid, t in state.get("tasks", {}).items():
    if t.get("status") not in ["RECONCILED", "FAILED_TERMINAL", "HUMAN_REQUIRED"]:
        t["status"] = "FAILED_TERMINAL"
        t["blocker"] = "CLEANUP_SWEEP"
        
for gid, g in state.get("goals", {}).items():
    if g.get("status") == "ACTIVE":
        g["status"] = "BLOCKED"
        if "workflow_plan" in g:
            for step in g["workflow_plan"]:
                if step.get("status") not in ["RECONCILED", "FAILED_TERMINAL", "HUMAN_REQUIRED"]:
                    step["status"] = "FAILED_TERMINAL"

with open("server/state/central_state.json", "w") as f:
    json.dump(state, f, indent=2)

print("Queue Swept to CLEAN_IDLE")
