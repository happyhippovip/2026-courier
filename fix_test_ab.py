import re
with open("tests/test_ab_reconcile_unlock.py", "r") as f:
    c = f.read()

# Add import
if "from scripts.integration_contract import _canonical_hash" not in c:
    c = "from scripts.integration_contract import _canonical_hash\n" + c

# The result dictionary definition
old_result = """    result = {
        "goal_id": claimed_a["goal_id"],
        "task_id": "task-A",
        "attempt_id": claimed_a["attempt_id"],
        "dispatch_id": claimed_a["dispatch_id"],
        "execution_ref": claimed_a.get("execution_ref", "exec-test"),
        "worker_id": "W-01",
        "run_id": "pid-test",
        "result_id": "result-A-1",
        "status": "SUCCESS",
        "artifacts": [
            {"path": "a.txt", "sha256": hashlib.sha256(b"a\\n").hexdigest()}
        ],
    }"""
new_result = """    result = {
        "goal_id": claimed_a["goal_id"],
        "task_id": "task-A",
        "attempt_id": claimed_a["attempt_id"],
        "dispatch_id": claimed_a["dispatch_id"],
        "execution_ref": claimed_a.get("execution_ref", "exec-test"),
        "worker_id": "W-01",
        "run_id": "pid-test",
        "status": "SUCCESS",
        "artifacts": [
            {"path": "a.txt", "sha256": hashlib.sha256(b"a\\n").hexdigest()}
        ],
        "runtime_identity": claimed_a["server_binding"]
    }
    result["result_id"] = f"result-{_canonical_hash(result)}\""""
c = c.replace(old_result, new_result)

c = c.replace('"result_id": "result-A-1",', '"result_id": result["result_id"],')

with open("tests/test_ab_reconcile_unlock.py", "w") as f:
    f.write(c)

