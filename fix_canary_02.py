import json
with open("central_state.json", "r") as f:
    state = json.load(f)
state["goals"]["goal-canary-02"]["status"] = "NEW"
with open("central_state.json", "w") as f:
    json.dump(state, f, indent=2)
