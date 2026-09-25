import re

for fn in ["tests/test_DLQ01_trust_boundary.py", "tests/test_DLQ02_freshness_bound.py"]:
    with open(fn, "r") as f:
        c = f.read()

    new_func = """from scripts.integration_contract import _canonical_hash

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
        "artifacts": [{"path": "a.txt", "sha256": hashlib.sha256(b"a\\n").hexdigest()}]
    }
    
    if "prompt_id" in claimed:
        res["prompt_id"] = claimed["prompt_id"]
        
    res["runtime_identity"] = claimed.get("server_binding", {"uid": "mock"})
    
    if result_id is None:
        expected = f"result-{_canonical_hash(res)}"
        res["result_id"] = expected
    else:
        res["result_id"] = result_id
        
    return res"""
    c = re.sub(r'def make_result\(claimed, result_id="res-1"\):.*?\}', new_func, c, flags=re.DOTALL)
    
    # Also fix the import dlq01_refresh
    if fn == "tests/test_DLQ02_freshness_bound.py":
        c = c.replace("from dlq01_refresh import record as base_record, base_guard", "")
        c = c.replace("import importlib.util\nimport sys\nimport time", "import importlib.util\nimport sys\nimport time\n\ndef get_base():\n    from dlq01_refresh import record as base_record, base_guard\n    return base_record, base_guard")
        
    with open(fn, "w") as f:
        f.write(c)
