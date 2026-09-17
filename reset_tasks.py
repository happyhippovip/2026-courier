import json
with open('server/state/central_state.json', 'r') as f:
    state = json.load(f)

for i in range(6, 11):
    task_id = f"task-p12-{i}-v2"
    if task_id in state["tasks"]:
        t = state["tasks"][task_id]
        t["status"] = "QUEUED"
        t["attempts"] = 0
        t["result"] = None
        t["blocker"] = None
        t["worker_id"] = None
        t["attempt_id"] = None

with open('server/state/central_state.json', 'w') as f:
    json.dump(state, f, indent=2)
print("Tasks 6-10 reset to QUEUED.")
