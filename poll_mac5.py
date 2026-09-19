import json, time
for _ in range(10):
    with open("server/state/central_state.json", "r") as f:
        state = json.load(f)
    g = state.get("goals", {}).get("goal-48f38acd")
    if g and g.get("status") == "DONE":
        print("MAC 5 DONE!")
        for t in g.get("workflow_plan", []):
            print(f"Task: {t.get('task_id')} - Status: {t.get('status')}")
        break
    time.sleep(3)
else:
    print("TIMEOUT!")
