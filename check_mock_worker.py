import json
with open("server/state/central_state.json", "r") as f:
    state = json.load(f)
w = state.get("workers", {}).get("FREE-MOCK-WORKER")
print(f"Mock Worker: {w}")
