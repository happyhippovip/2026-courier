import re

def update_file(filename):
    with open(filename, "r") as f:
        content = f.read()

    new_make_res = """from scripts.integration_contract import _canonical_hash
def make_result(claimed, result_id=None):
    res = {
        "goal_id": claimed["goal_id"],
        "task_id": claimed["task_id"],
        "attempt_id": claimed["attempt_id"],
        "dispatch_id": claimed["dispatch_id"],
        "execution_ref": claimed.get("execution_ref", "exec-test"),
        "worker_id": claimed["worker_id"],
        "run_id": "pid-test",
        "status": "SUCCESS",
        "artifacts": [{"path": "a.txt", "sha256": hashlib.sha256(b"a\\n").hexdigest()}],
        "runtime_identity": claimed.get("server_binding", {"uid": "mock"}),
        "prompt_id": claimed.get("prompt_id")
    }
    
    # Calculate canonical result_id just like validate_durable_result expects
    if result_id is None:
        identity = {
            "goal_id": res["goal_id"],
            "task_id": res["task_id"],
            "attempt_id": res["attempt_id"],
            "dispatch_id": res["dispatch_id"],
            "execution_ref": res["execution_ref"],
            "worker_id": res["worker_id"],
            "run_id": res["run_id"],
            "status": res["status"],
            "artifacts": res["artifacts"],
            "runtime_identity": res["runtime_identity"]
        }
        if res.get("prompt_id"): identity["prompt_id"] = res["prompt_id"]
        res["result_id"] = f"result-{_canonical_hash(identity)}"
    else:
        res["result_id"] = result_id
        
    return res"""

    content = re.sub(r'def make_result\(claimed, result_id="res-1"\):.*?\}\n', new_make_res + "\n", content, flags=re.DOTALL)
    
    with open(filename, "w") as f:
        f.write(content)

update_file("tests/test_DLQ01_trust_boundary.py")
update_file("tests/test_DLQ02_freshness_bound.py")
print("Patched!")
