import json
with open("server/state/central_state.json", "r") as f:
    state = json.load(f)
for gid, g in state.get("goals", {}).items():
    if g.get("goal_text") == "Mac Dependency Test":
        for t in g.get("workflow_plan", []):
            print(f"Task: {t.get('task_id')} - Status: {t.get('status')} - Depends On: {t.get('depends_on')}")
