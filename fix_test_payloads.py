import os, glob, re

for filename in glob.glob("tests/test_*.py"):
    with open(filename, "r") as f:
        code = f.read()
    
    # We want to find dictionaries passed to /tasks/verify and add received_runtime_identity.
    # Usually they look like:
    # {"task_id": claimed["task_id"], "verifier_id": "V-01", "result_id": "res-1", "verdict": "PASS", "artifacts": result_json["artifacts"]}
    # Or verification = {...}
    
    # Let's just do a blanket regex: if there's a payload dict that contains "verifier_id", we can inject it?
    # Actually, it's safer to just inject it where we see `http.post("/tasks/verify", ... json=...)`
    
    # Instead of fancy regex, let's just replace the exact payloads
    # Let's see what is inside test_server_integration_contract.py
    
    # Let's replace `verification = {` with `verification = {"received_runtime_identity": task["server_binding"],`
    code = code.replace(
        'verification = {\n            "task_id":',
        'verification = {\n            "received_runtime_identity": task["server_binding"],\n            "task_id":'
    )
    code = code.replace(
        'verification = {\n        "task_id":',
        'verification = {\n        "received_runtime_identity": task["server_binding"],\n        "task_id":'
    )
    
    # For DLQ01:
    code = code.replace(
        '"task_id": claimed["task_id"], "verifier_id":',
        '"received_runtime_identity": claimed.get("server_binding", {"sha": "fake", "runtime": "fake"}), "task_id": claimed["task_id"], "verifier_id":'
    )
    
    # For ab_reconcile:
    code = code.replace(
        'verify_req = {"task_id":',
        'verify_req = {"received_runtime_identity": claimed["server_binding"], "task_id":'
    )
    
    # Let's just save
    with open(filename, "w") as f:
        f.write(code)

