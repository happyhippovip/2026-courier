from server.app import app
from scripts.integration_contract import prepare_task, validate_durable_result
import json

task = {
    "task_id": "t1", "goal_id": "g1", "target_capability": "linux", "artifacts": []
}
task = prepare_task(task)
task["artifacts"] = [] # override to empty

result = {
    "goal_id": task["goal_id"], "task_id": task["task_id"], "attempt_id": task["attempt_id"],
    "dispatch_id": task["dispatch_id"], "worker_id": task["worker_id"],
    "run_id": "r1", "status": "SUCCESS", "artifacts": []
}
result["result_id"] = "result-123"

try:
    validate_durable_result(task, result)
    print("SUCCESS")
except Exception as e:
    print(f"FAILED: {e}")
