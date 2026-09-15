import json
with open('central_state.json', 'r') as f:
    state = json.load(f)
if "goals" not in state:
    state["goals"] = {}
with open('central_state.json', 'w') as f:
    json.dump(state, f, indent=2)
