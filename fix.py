import json
with open("central_state.json", "r") as f:
    state = json.load(f)
for task in state["goals"]["goal-canary-01"]["workflow_plan"]:
    task["goal_id"] = "goal-canary-01"
with open("central_state.json", "w") as f:
    json.dump(state, f, indent=2)
