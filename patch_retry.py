import re, hashlib, json

with open("tests/test_server_integration_contract.py", "r") as f:
    content = f.read()

replacement = """failed["status"] = "FAILED"
    failed["artifacts"] = []
    
    identity = {k: failed.get(k) for k in ("goal_id", "task_id", "attempt_id", "dispatch_id", "execution_ref", "worker_id", "run_id", "status", "artifacts", "runtime_identity")}
    rid = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    failed["result_id"] = f"result-{rid}"
"""

content = content.replace('failed["status"] = "FAILED"\n    failed["artifacts"] = []', replacement)

with open("tests/test_server_integration_contract.py", "w") as f:
    f.write(content)
