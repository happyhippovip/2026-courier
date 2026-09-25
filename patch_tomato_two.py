import re
with open("tests/test_tomato_two_torture.py", "r") as f:
    content = f.read()

replacement = """        base_payload = {
            "worker_id": launchd_wid,
            "goal_id": seq_goal_id,
            "task_id": task_seq1,
            "dispatch_id": t1_final.get("dispatch_id"),
            "attempt_id": t1_final.get("attempt_id"),
            "execution_ref": t1_final.get("execution_ref"),
            "run_id": "duplicate-run-test",
            "status": "SUCCESS",
            "artifacts": [],
            "runtime_identity": runtime_id
        }
        import json, hashlib
        identity_dup = {k: base_payload.get(k) for k in ("goal_id", "task_id", "attempt_id", "dispatch_id", "execution_ref", "worker_id", "run_id", "status", "artifacts", "runtime_identity")}
        rid_dup = hashlib.sha256(json.dumps(identity_dup, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        payload = dict(base_payload, result_id=f"result-{rid_dup}", provider="mac_native", raw_result={"status": "SUCCESS"})
        dup_res = http_post("/tasks/result", payload)"""

# In test_tomato_two_torture.py, the code looks like:
#        dup_res = http_post("/tasks/result", {
#            "worker_id": launchd_wid,
#            "goal_id": seq_goal_id,
#            "task_id": task_seq1,
#            "dispatch_id": t1_final.get("dispatch_id"),
#            "attempt_id": t1_final.get("attempt_id"),
#            "execution_ref": t1_final.get("execution_ref"),
#            "run_id": "duplicate-run-test",
#            "result_id": "duplicate-res-test",
#            "status": "SUCCESS",
#            "artifacts": [],
#            "provider": "mac_native",
#            "raw_result": {"status": "SUCCESS"}
#        })

content = re.sub(r'        dup_res = http_post\("/tasks/result", \{.*?"raw_result": \{"status": "SUCCESS"\}\n        \}\)', replacement, content, flags=re.DOTALL)

with open("tests/test_tomato_two_torture.py", "w") as f:
    f.write(content)
