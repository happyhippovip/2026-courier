import re
with open("tests/test_routing_acceptance_v1.py", "r") as f:
    content = f.read()

import_repl = """from scripts.integration_contract import _canonical_hash

def result_for(claimed, worker_id, result_id, status, stderr=None):
    from server.app import SERVER_BINDING
    result = {
        "goal_id": claimed["goal_id"],
        "task_id": claimed["task_id"],
        "attempt_id": claimed["attempt_id"],
        "dispatch_id": claimed["dispatch_id"],
        "execution_ref": claimed["execution_ref"],
        "worker_id": worker_id,
        "run_id": f"run-{result_id}",
        "status": status,
        "runtime_identity": SERVER_BINDING,
        "artifacts": [],
    }
    identity = dict(result)
    result["result_id"] = f"result-{_canonical_hash(identity)}"
    
    if stderr is not None:
        result["stderr"] = stderr
    return result
"""

content = re.sub(r'def result_for\(claimed, worker_id, result_id, status, stderr=None\):.*?return result\n', import_repl, content, flags=re.DOTALL)

with open("tests/test_routing_acceptance_v1.py", "w") as f:
    f.write(content)
