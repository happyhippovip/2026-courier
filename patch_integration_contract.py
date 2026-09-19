import re

with open("scripts/integration_contract.py", "r") as f:
    content = f.read()

# 1. Update verify_result to include runtime_identity
old_verify = """
    identity = {
        "goal_id": result["goal_id"],
        "task_id": result["task_id"],
        "attempt_id": result["attempt_id"],
        "dispatch_id": result["dispatch_id"],
        "execution_ref": result["execution_ref"],
        "worker_id": result["worker_id"],
        "run_id": result["run_id"],
        "status": result["status"],
        "artifacts": result.get("artifacts", [])
    }
"""
new_verify = """
    identity = {
        "goal_id": result["goal_id"],
        "task_id": result["task_id"],
        "attempt_id": result["attempt_id"],
        "dispatch_id": result["dispatch_id"],
        "execution_ref": result["execution_ref"],
        "worker_id": result["worker_id"],
        "run_id": result["run_id"],
        "status": result["status"],
        "artifacts": result.get("artifacts", []),
        "runtime_identity": task.get("server_binding")
    }
"""
content = content.replace(old_verify, new_verify)

# 2. Update validate_durable_result to enforce hash
old_validate = """
def validate_durable_result(task, result):
    if not isinstance(result.get("result_id"), str) or not result["result_id"]:
        raise ContractError("result_id must be a non-empty string")
"""
new_validate = """
def validate_durable_result(task, result):
    if not isinstance(result.get("result_id"), str) or not result["result_id"]:
        raise ContractError("result_id must be a non-empty string")
        
    identity = {
        "goal_id": result.get("goal_id"),
        "task_id": result.get("task_id"),
        "attempt_id": result.get("attempt_id"),
        "dispatch_id": result.get("dispatch_id"),
        "execution_ref": result.get("execution_ref"),
        "worker_id": result.get("worker_id"),
        "run_id": result.get("run_id"),
        "status": result.get("status"),
        "artifacts": result.get("artifacts", []),
        "runtime_identity": result.get("runtime_identity")
    }
    
    if result.get("runtime_identity") != task.get("server_binding"):
        raise ContractError("runtime_identity mismatch")
        
    expected_result_id = f"result-{_canonical_hash(identity)}"
    if result.get("result_id") != expected_result_id:
        raise ContractError(f"result_id cryptographic mismatch. Expected {expected_result_id}")
"""
content = content.replace(old_validate, new_validate)

with open("scripts/integration_contract.py", "w") as f:
    f.write(content)
