import json

with open("central_state.json", "r") as f:
    state = json.load(f)

state["goals"]["goal-canary-02"] = {
  "workflow_plan": [
    {
      "target_capability": "windows",
      "task_id": "task-canary-03",
      "goal_id": "goal-canary-02",
      "description": "native canary step C (Windows)"
    },
    {
      "target_capability": "mac",
      "task_id": "task-canary-04",
      "goal_id": "goal-canary-02",
      "description": "native canary step D (Mac)"
    }
  ],
  "goal_id": "goal-canary-02",
  "goal_text": "Run two step cross-machine canary",
  "status": "QUEUED",
  "current_step_index": 0
}

with open("central_state.json", "w") as f:
    json.dump(state, f, indent=2)

print("goal-canary-02 injected.")
