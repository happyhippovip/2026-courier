import json
with open("server/state/central_state.json", "r") as f:
    state = json.load(f)
g = state.get("goals", {}).get("goal-c4b3acdf")
if g:
    print(f"Goal Status: {g.get('status')}")
    for t in g.get("workflow_plan", []):
        print(f"{t.get('task_id')}: {t.get('status')}")
