import uuid
import hashlib
import json
with open("tests/test_auto_replenishment.py", "r") as f:
    c = f.read()

# Add import
if "from scripts.integration_contract import _canonical_hash" not in c:
    c = "from scripts.integration_contract import _canonical_hash\n" + c

old_result = """        result_payload = {
            "task_id": task_id,
            "worker_id": "linux-worker",
            "status": "SUCCESS",
            "result_file_path": f"/tmp/result_{task_id}.json",
            "stderr": "",
            "stdout": "success",
            "artifacts": [],
            "attempt_id": task.get("attempt_id"),
            "dispatch_id": task.get("dispatch_id"),
            "execution_ref": task.get("execution_ref"),
            "goal_id": task.get("goal_id"),
            "result_id": f"res-{uuid.uuid4().hex[:8]}",
            "run_id": f"run-{uuid.uuid4().hex[:8]}"
        }"""

new_result = """        result_payload = {
            "task_id": task_id,
            "worker_id": "linux-worker",
            "status": "SUCCESS",
            "result_file_path": f"/tmp/result_{task_id}.json",
            "stderr": "",
            "stdout": "success",
            "artifacts": [],
            "attempt_id": task.get("attempt_id"),
            "dispatch_id": task.get("dispatch_id"),
            "execution_ref": task.get("execution_ref"),
            "goal_id": task.get("goal_id"),
            "run_id": f"run-{uuid.uuid4().hex[:8]}",
            "runtime_identity": task.get("server_binding")
        }
        identity = {
            "goal_id": result_payload.get("goal_id"),
            "task_id": result_payload.get("task_id"),
            "attempt_id": result_payload.get("attempt_id"),
            "dispatch_id": result_payload.get("dispatch_id"),
            "execution_ref": result_payload.get("execution_ref"),
            "worker_id": result_payload.get("worker_id"),
            "run_id": result_payload.get("run_id"),
            "status": result_payload.get("status"),
            "artifacts": result_payload.get("artifacts", []),
            "runtime_identity": result_payload.get("runtime_identity")
        }
        if "batch_id" in task: identity["batch_id"] = task["batch_id"]
        if "prompt_id" in task: identity["prompt_id"] = task["prompt_id"]
        result_payload["result_id"] = f"result-{_canonical_hash(identity)}\""""

c = c.replace(old_result, new_result)

with open("tests/test_auto_replenishment.py", "w") as f:
    f.write(c)

