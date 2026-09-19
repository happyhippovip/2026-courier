import json
with open("server/state/central_state.json", "r") as f:
    state = json.load(f)
for gid, g in state.get("goals", {}).items():
    if g.get("goal_text") == "Mac Dependency Test":
        print(json.dumps(g, indent=2))
