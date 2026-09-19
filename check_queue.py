import json

try:
    with open("server/state/central_state.json", "r") as f:
        state = json.load(f)
except BaseException:
    print("NO_STATE")
    exit(0)

active_goals = [g for g in state.get("goals", {}).values() if g.get("status") == "ACTIVE"]
print(f"ACTIVE GOALS: {len(active_goals)}")
for g in active_goals:
    print(f"Goal: {g.get('goal_id')} - {g.get('goal_text')}")

dispatched = [t for t in state.get("tasks", {}).values() if t.get("status") == "DISPATCHED"]
print(f"DISPATCHED TASKS: {len(dispatched)}")
