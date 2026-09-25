import re
with open("tests/test_motor_eligibility_v1.py", "r") as f:
    content = f.read()

replacement = """
    import hashlib, json, server.app
    base_res = {
        "goal_id": claimed["goal_id"],
        "task_id": claimed["task_id"],
        "attempt_id": claimed["attempt_id"],
        "dispatch_id": claimed["dispatch_id"],
        "execution_ref": claimed["execution_ref"],
        "worker_id": claimed["worker_id"],
        "run_id": "run-1",
        "status": "SUCCESS",
        "artifacts": [],
        "runtime_identity": server.app.SERVER_BINDING
    }
    rid = hashlib.sha256(json.dumps(base_res, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    result = dict(base_res, result_id=f"result-{rid}")
"""

content = re.sub(r'    result = \{\n        "goal_id": claimed\["goal_id"\],\n        "task_id": claimed\["task_id"\],\n        "attempt_id": claimed\["attempt_id"\],\n        "dispatch_id": claimed\["dispatch_id"\],\n        "execution_ref": claimed\["execution_ref"\],\n        "worker_id": "W",\n        "run_id": "run-1",\n        "result_id": "result-1",\n        "status": "SUCCESS",\n        "artifacts": \[\],\n    \}', replacement, content)

with open("tests/test_motor_eligibility_v1.py", "w") as f:
    f.write(content)
