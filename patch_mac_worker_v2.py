import re

with open("scripts/mac_worker/daemon.py", "r") as f:
    content = f.read()

replacement = """
                        "execution_ref": task.get("execution_ref"),
"""

patch = """
                    run_id = str(uuid.uuid4())
                    h = hashlib.sha256()
                    h.update(config["WORKER_ID"].encode())
                    h.update(task.get("task_id", "").encode())
                    h.update(task.get("dispatch_id", "").encode())
                    h.update(task.get("attempt_id", "").encode())
                    h.update(task.get("execution_ref", "").encode())
                    h.update(run_id.encode())
                    h.update(task.get("server_binding", "").encode())
                    calculated_result_id = "result-" + h.hexdigest()

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

# We'll replace the whole payload block
pattern = re.compile(r'                    payload = \{.*?"raw_result": result\n                    \}', re.DOTALL)
new_content = pattern.sub(patch.strip('\n'), content)

with open("scripts/mac_worker/daemon.py", "w") as f:
    f.write(new_content)

print("Patched daemon.py successfully")
