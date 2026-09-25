import re
with open("tests/test_server_integration_contract.py", "r") as f:
    content = f.read()

replacement = """def durable_result(task):
    import hashlib, json, server.app
    base_res = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "execution_ref": task.get("execution_ref", "exec-mock"),
        "worker_id": task["worker_id"],
        "run_id": "pid-123",
        "status": "SUCCESS",
        "artifacts": [
            {"path": "bounded.txt", "sha256": hashlib.sha256(b"bounded\\n").hexdigest()}
        ],
        "runtime_identity": server.app.SERVER_BINDING
    }
    identity = {k: base_res.get(k) for k in ("goal_id", "task_id", "attempt_id", "dispatch_id", "execution_ref", "worker_id", "run_id", "status", "artifacts", "runtime_identity")}
    rid = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return dict(base_res, result_id=f"result-{rid}")
"""
content = re.sub(r'def durable_result\(task\):.*?    \}', replacement, content, flags=re.DOTALL)
# Also need to fix any verify calls that hardcode "result-1"
content = content.replace('"result_id": "result-1"', '"result_id": result["result_id"], "received_runtime_identity": server.app.SERVER_BINDING')
content = content.replace('result["result_id"] = "result-1"', 'pass') # Actually, there is a place where they might do this

with open("tests/test_server_integration_contract.py", "w") as f:
    f.write(content)
