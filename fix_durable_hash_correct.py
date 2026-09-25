import re
with open("tests/test_server_integration_contract.py", "r") as f:
    text = f.read()

durable_result_code = r"""
def durable_result(task):
    import hashlib
    base = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "execution_ref": task.get("execution_ref", "exec-mock"),
        "worker_id": task["worker_id"],
        "status": "SUCCESS",
        "artifacts": [
            {"path": "bounded.txt", "sha256": hashlib.sha256(b"bounded\n").hexdigest()}
        ],
        "runtime_identity": task.get("server_binding")
    }
    ident = dict(base)
    base["run_id"] = "pid-123"
    base["result_id"] = "result-" + _canonical_hash(ident)
    return base
"""

# Replace the old durable_result
text = re.sub(r'def durable_result\(task\):.*?return base', durable_result_code.strip(), text, flags=re.DOTALL)

with open("tests/test_server_integration_contract.py", "w") as f:
    f.write(text)
