import json
with open("server/state/central_state.json", "r") as f:
    state = json.load(f)
t = state.get("tasks", {}).get("WP_REPO")
if t:
    print(json.dumps(t, indent=2))
