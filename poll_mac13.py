import json, time
for _ in range(15):
    with open("server/state/central_state.json", "r") as f:
        state = json.load(f)
    g = state.get("goals", {}).get("goal-1f347b04")
    if g and g.get("status") == "DONE":
        print("MAC 13 DONE!")
        for t in g.get("workflow_plan", []):
            task_state = state.get("tasks", {}).get(t.get('task_id'), {})
            print(f"Task: {t.get('task_id')} - Status: {t.get('status')} - Worker: {task_state.get('worker_id')}")
        break
    time.sleep(3)
else:
    print("TIMEOUT!")
