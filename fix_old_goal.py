import json

with open("server/state/central_state.json", "r") as f:
    state = json.load(f)

for g in list(state["goals"].keys()):
    if state["goals"][g]["status"] == "ACTIVE" and g != "goal-10f2ce1d":
        state["goals"][g]["status"] = "FAILED"

for t in state["tasks"].values():
    if t.get("owner_scope") == "TEST" and t.get("status") == "DISPATCHED" and t.get("goal_id") != "goal-10f2ce1d":
        t["status"] = "FAILED"

with open("server/state/central_state.json", "w") as f:
    json.dump(state, f)
