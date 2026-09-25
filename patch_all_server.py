import re
with open("tests/test_server_integration_contract.py", "r") as f:
    text = f.read()

# Fix import
text = "from scripts.integration_contract import _canonical_hash\n" + text

# Fix durable_result using split to avoid re.sub escaping
parts = text.split("def durable_result(task):")
before = parts[0]
after_def = parts[1]
after = after_def[after_def.find("def test_worker_success"):]

durable_result_code = """def durable_result(task):
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
            {"path": "bounded.txt", "sha256": hashlib.sha256(b"bounded\\n").hexdigest()}
        ],
        "runtime_identity": task.get("server_binding", "MAC-01")
    }
    ident = dict(base)
    base["run_id"] = "pid-123"
    base["result_id"] = "result-" + _canonical_hash(ident)
    return base

"""

text = before + durable_result_code + after

# Fix verification
text = text.replace('"artifacts": result["artifacts"],', '"artifacts": result["artifacts"],\n        "received_runtime_identity": task.get("server_binding", "MAC-01"),')

# Fix retry test
old_retry = """
        failed = durable_result(task)
        failed["status"] = "FAILED"
        failed["artifacts"] = []
"""
new_retry = """
        failed = durable_result(task)
        failed["status"] = "FAILED"
        failed["artifacts"] = []
        ident = {k: v for k, v in failed.items() if k not in ("run_id", "result_id")}
        failed["result_id"] = "result-" + _canonical_hash(ident)
"""
text = text.replace(old_retry.strip(), new_retry.strip())

with open("tests/test_server_integration_contract.py", "w") as f:
    f.write(text)
