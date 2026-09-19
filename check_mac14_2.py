import json
with open("server/state/central_state.json", "r") as f:
    state = json.load(f)
t = state.get("tasks", {}).get("CHEAP_LINUX_TASK_2")
if t:
    print(f"Task Worker ID: {t.get('worker_id')}")
else:
    print("Task not found")
