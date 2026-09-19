import re

with open("tests/test_turbo_queue_concurrency.py", "r") as f:
    content = f.read()

if "from scripts.integration_contract import _canonical_hash" not in content:
    content = "from scripts.integration_contract import _canonical_hash\n" + content

old_result = """                result = {
                    "goal_id": task["goal_id"], "task_id": tid, "attempt_id": task["attempt_id"],
                    "dispatch_id": task["dispatch_id"], "execution_ref": task["execution_ref"],
                    "worker_id": w_id, "run_id": f"run_{tid}", "result_id": f"res_{tid}",
                    "status": "SUCCESS", "artifacts": [], "runtime_identity": task.get("server_binding")
                }"""
new_result = """                result = {
                    "goal_id": task["goal_id"], "task_id": tid, "attempt_id": task["attempt_id"],
                    "dispatch_id": task["dispatch_id"], "execution_ref": task["execution_ref"],
                    "worker_id": w_id, "run_id": f"run_{tid}",
                    "status": "SUCCESS", "artifacts": [], "runtime_identity": task.get("server_binding")
                }
                result["result_id"] = f"result-{_canonical_hash(result)}"
                
                # store the valid result_id globally for the verifier to use later
                app_state = server.app.load_state()
                if "res_ids" not in app_state:
                    app_state["res_ids"] = {}
                app_state["res_ids"][tid] = result["result_id"]
                server.app.save_state(app_state)"""
content = content.replace(old_result, new_result)

old_verify_1 = """            "task_id": tid, "verifier_id": "v1", "result_id": f"res_{tid}","""
new_verify_1 = """            "task_id": tid, "verifier_id": "v1", "result_id": state["res_ids"][tid],"""
content = content.replace(old_verify_1, new_verify_1)

old_verify_2 = """        "task_id": "A", "verifier_id": "v1", "result_id": "res_A","""
new_verify_2 = """        "task_id": "A", "verifier_id": "v1", "result_id": state["res_ids"]["A"],"""
content = content.replace(old_verify_2, new_verify_2)

with open("tests/test_turbo_queue_concurrency.py", "w") as f:
    f.write(content)
