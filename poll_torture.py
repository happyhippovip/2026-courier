import json, time
for _ in range(10):
    with open("server/state/central_state.json", "r") as f:
        state = json.load(f)
    g = state.get("goals", {}).get("goal-8e0cc296")
    if g and g.get("status") == "DONE":
        print("TORTURE DONE!")
        workers_used = set()
        for t in g.get("workflow_plan", []):
            if t.get("worker_id"): workers_used.add(t.get("worker_id"))
        print(f"Workers used: {workers_used}")
        break
    time.sleep(3)
else:
    print("TIMEOUT!")
