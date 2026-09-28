import time
from server.app import load_state, save_state
state = load_state()
goal_id = "g1"
state["goals"][goal_id] = {
    "status": "BLOCKED",
    "workflow_plan": [
        {"task_id": "t1", "status": "RECONCILED"},
        {"task_id": "t2", "status": "QUEUED", "target_agent": "windows"}
    ],
    "current_step_index": 1
}
save_state(state)
