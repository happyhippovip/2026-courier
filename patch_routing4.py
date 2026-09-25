import re
with open("tests/test_routing_acceptance_v1.py", "r") as f:
    content = f.read()

import_repl = """from server.app import SERVER_BINDING
from scripts.integration_contract import _canonical_hash

def result_for(claimed, worker_id, result_id, status, stderr=None):
    base_res = {
        "goal_id": claimed["goal_id"],
        "task_id": claimed["task_id"],
        "attempt_id": claimed["attempt_id"],
        "dispatch_id": claimed["dispatch_id"],
        "execution_ref": claimed["execution_ref"],
        "worker_id": worker_id,
        "run_id": f"run-{result_id}",
        "status": status,
        "runtime_identity": SERVER_BINDING,
    }
    if stderr:
        base_res["stderr"] = stderr
        
    identity = {
        "goal_id": claimed["goal_id"],
        "task_id": claimed["task_id"],
        "attempt_id": claimed["attempt_id"],
        "dispatch_id": claimed["dispatch_id"],
        "execution_ref": claimed["execution_ref"],
        "worker_id": worker_id,
        "run_id": f"run-{result_id}",
        "status": status,
        "artifacts": [],
        "runtime_identity": SERVER_BINDING
    }
    
    base_res["result_id"] = f"result-{_canonical_hash(identity)}"
    return base_res

def _dummy_result_for"""

content = re.sub(r'from server\.app import SERVER_BINDING\nimport hashlib\nimport json\n\ndef result_for.*?return base_res\n\ndef _dummy_result_for', import_repl, content, flags=re.DOTALL)

with open("tests/test_routing_acceptance_v1.py", "w") as f:
    f.write(content)
