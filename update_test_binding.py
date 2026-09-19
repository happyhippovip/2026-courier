import re
with open("tests/test_binding_contract.py", "r") as f:
    content = f.read()
    
# We need to construct the payload using generate_task_identity logic
# But we can just import _canonical_hash
patch = """
    from scripts.integration_contract import _canonical_hash
    base_payload = {
        "worker_id": "W1",
        "task_id": task1["task_id"],
        "status": "SUCCESS",
        "artifacts": [{"path": "relative_evidence1.txt", "sha256": "a" * 64}],
        "attempt_id": task1["attempt_id"],
        "dispatch_id": task1["dispatch_id"],
        "execution_ref": task1["execution_ref"],
        "goal_id": task1["goal_id"],
        "run_id": "run-1",
        "runtime_identity": task1["server_binding"]
    }
    identity = dict(base_payload)
    base_payload["result_id"] = f"result-{_canonical_hash(identity)}"
"""
content = re.sub(r'    base_payload = \{[^\}]+\}', patch.strip(), content)
with open("tests/test_binding_contract.py", "w") as f:
    f.write(content)
