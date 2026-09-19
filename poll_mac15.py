import json, time
for _ in range(15):
    with open("server/state/central_state.json", "r") as f:
        state = json.load(f)
    g = state.get("goals", {}).get("goal-c4773cc8")
    if g and g.get("status") == "DONE":
        print("MAC 15 DONE!")
        for t in g.get("workflow_plan", []):
            task_state = state.get("tasks", {}).get(t.get('task_id'), {})
            print(f"Task: {t.get('task_id')} - Status: {task_state.get('status')}")
        break
    time.sleep(3)
else:
    print("TIMEOUT!")
