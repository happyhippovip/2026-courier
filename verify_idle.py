import json

with open("server/state/central_state.json", "r") as f:
    state = json.load(f)

active_goals = 0
active_tasks = 0

for g in state.get("goals", {}).values():
    if g.get("status") == "ACTIVE":
        active_goals += 1

for t in state.get("tasks", {}).values():
    if t.get("status") not in ["RECONCILED", "FAILED_TERMINAL", "HUMAN_REQUIRED"]:
        active_tasks += 1

print(f"ACTIVE_GOALS: {active_goals}")
print(f"ACTIVE_TASKS: {active_tasks}")
