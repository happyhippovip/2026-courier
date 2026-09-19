import json, time
for i in range(15):
    with open("server/state/central_state.json", "r") as f:
        state = json.load(f)
    g = state.get("goals", {}).get("goal-c4b3acdf")
    if g:
        print(f"--- Iteration {i} ---")
        for t in g.get("workflow_plan", []):
            print(f"{t.get('task_id')}: {t.get('status')}")
        if g.get("status") == "DONE":
            print("MAC 7 DONE!")
            break
    time.sleep(1)
