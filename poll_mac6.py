import json, time
for _ in range(15):
    with open("server/state/central_state.json", "r") as f:
        state = json.load(f)
    g = state.get("goals", {}).get("goal-18fb85ed")
    if g and g.get("status") == "BLOCKED":
        print("MAC 6 BLOCKED (Expected)!")
        for t in g.get("workflow_plan", []):
            print(f"Task: {t.get('task_id')} - Status: {t.get('status')} - Attempts: {t.get('attempts')}")
        break
    time.sleep(4)
else:
    print("TIMEOUT!")
