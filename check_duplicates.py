import json
with open("server/state/central_state.json", "r") as f:
    state = json.load(f)
for gid, g in state.get("goals", {}).items():
    print(f"Goal: {g.get('goal_text')} - Status: {g.get('status')} - Tasks: {len(g.get('workflow_plan', []))}")
