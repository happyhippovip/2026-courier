import json

with open("server/state/central_state.json", "r") as f:
    state = json.load(f)

state["workers"] = {}

with open("server/state/central_state.json", "w") as f:
    json.dump(state, f, indent=2)

print("Cleared workers")
