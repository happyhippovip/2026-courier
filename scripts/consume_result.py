import json
import sys

run_id = sys.argv[1]
try:
    with open('result.json', 'r') as f:
        result = json.load(f)
except Exception as e:
    result = {"error": str(e)}

try:
    with open('central_state.json', 'r') as f:
        state = json.load(f)
except Exception:
    state = {"tasks": {}}

task_id = "task-vollautomatik-002"
state["tasks"][task_id] = {
    "task_id": task_id,
    "attempt_id": "attempt-001",
    "worker_id": "revenue-v1-github",
    "platform": "github_actions",
    "dispatch_ref": "gh_workflow_run",
    "execution_ref": run_id,
    "state": "RECONCILED",
    "result_ref": "result.json",
    "last_transition": "AUTOMATIC_CONSUMPTION",
    "next_explicit_transition": "HUMAN_REVIEW_REQUIRED",
    "real_wall": "HUMAN_REVIEW_REQUIRED",
    "cost": "free_tier"
}

with open('central_state.json', 'w') as f:
    json.dump(state, f, indent=2)

print("Result consumed automatically.")
