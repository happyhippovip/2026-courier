import re

with open("scripts/mac_worker/daemon.py", "r") as f:
    content = f.read()

patch = """
                    run_id = str(uuid.uuid4())
                    
                    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                    from integration_contract import _canonical_hash
                    
                    identity_payload = {
                        "goal_id": task.get("goal_id"),
                        "task_id": task["task_id"],
                        "attempt_id": task.get("attempt_id"),
                        "dispatch_id": task.get("dispatch_id"),
                        "execution_ref": task.get("execution_ref"),
                        "worker_id": config["WORKER_ID"],
                        "run_id": run_id,
                        "status": result.get("status", "FAILED"),
                        "artifacts": artifact_evidence,
                        "runtime_identity": task.get("server_binding")
                    }
                    calculated_result_id = "result-" + _canonical_hash(identity_payload)

                    payload = {
                        "worker_id": config["WORKER_ID"],
                        "goal_id": task.get("goal_id"),
                        "task_id": task["task_id"],
                        "dispatch_id": task.get("dispatch_id"),
                        "runtime_identity": task.get("server_binding"),
                        "attempt_id": task.get("attempt_id"),
                        "execution_ref": task.get("execution_ref"),
                        "run_id": run_id,
                        "result_id": calculated_result_id,
                        "status": result.get("status", "FAILED"),
                        "artifacts": artifact_evidence,
                        "provider": "mac_" + result.get("execution_mode", "unknown").lower(),
                        "raw_result": result
                    }
"""

pattern = re.compile(r'                    run_id = str\(uuid.uuid4\(\)\).*?raw_result": result\n                    \}', re.DOTALL)
new_content = pattern.sub(patch.strip('\n'), content)

with open("scripts/mac_worker/daemon.py", "w") as f:
    f.write(new_content)

print("Patched daemon.py successfully")
