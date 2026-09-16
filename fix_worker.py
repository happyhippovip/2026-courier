import json

with open("server/state/central_state.json", "r") as f:
    state = json.load(f)

for w in state["workers"].values():
    if w.get("current_task") == "task_A":
        w["current_task"] = None
        w["available"] = True

with open("server/state/central_state.json", "w") as f:
    json.dump(state, f)
