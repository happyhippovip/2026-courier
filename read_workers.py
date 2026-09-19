import json
with open("server/state/central_state.json", "r") as f:
    state = json.load(f)
for wid, w in state.get("workers", {}).items():
    print(wid, w.get("platform"), w.get("last_seen"), w.get("available"))
