import json, time
time.sleep(3)
with open("server/state/central_state.json", "r") as f:
    state = json.load(f)
g = state.get("goals", {}).get("goal-71e2f2c4")
if g:
    for t in g.get("workflow_plan", []):
        print(f"Task: {t.get('task_id')} - Status: {t.get('status')}")
