import json

try:
    with open("server/state/central_state.json", "r") as f:
        # If it fails, we will catch it
        json.load(f)
except BaseException:
    print("Fixing...")
    # Just recreate empty state
    state = {
        "schema_version": 2,
        "workers": {},
        "tasks": {},
        "goals": {},
        "resource_owners": {}
    }
    with open("server/state/central_state.json", "w") as f:
        json.dump(state, f)
