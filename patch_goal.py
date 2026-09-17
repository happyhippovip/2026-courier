import json
with open('server/state/central_state.json', 'r') as f:
    state = json.load(f)

goal = state["goals"]["goal-7125b706"]
goal["status"] = "ACTIVE"
for step in goal["workflow_plan"]:
    if step["status"] == "FAILED_TERMINAL":
        step["status"] = "QUEUED"

with open('server/state/central_state.json', 'w') as f:
    json.dump(state, f, indent=2)
print("Goal and workflow plan reset.")
