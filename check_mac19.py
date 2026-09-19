import json
with open("server/state/central_state.json", "r") as f:
    state = json.load(f)
g = state.get("goals", {}).get("goal-a2548537")
if g:
    print(f"Goal Status: {g.get('status')}")
    for t in g.get("workflow_plan", []):
        task_state = state.get("tasks", {}).get(t.get('task_id'), {})
        print(f"Task: {t.get('task_id')} | Status: {task_state.get('status')} | Blocker: {task_state.get('blocker')}")
