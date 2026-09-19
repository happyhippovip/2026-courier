import json
with open("server/state/central_state.json", "r") as f:
    state = json.load(f)
w = state.get("workers", {}).get("MAC-MACBOOK-PRO-VON-USER-EDEA96")
print(json.dumps(w, indent=2))
