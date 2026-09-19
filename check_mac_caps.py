import json
with open("server/state/central_state.json", "r") as f:
    state = json.load(f)
for wid, w in state.get("workers", {}).items():
    if "mac" in w.get("platform", "").lower():
        print(f"Worker: {wid}")
        print(f"Capabilities: {w.get('capabilities')}")
