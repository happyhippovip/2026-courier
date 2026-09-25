with open("tests/test_server_integration_contract.py", "r") as f:
    lines = f.readlines()

new_lines = ["from scripts.integration_contract import _canonical_hash\n"]
in_durable = False
for line in lines:
    if line.startswith("def durable_result(task):"):
        in_durable = True
        new_lines.append("""def durable_result(task):
    import hashlib
    base = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "execution_ref": task.get("execution_ref", "exec-mock"),
        "worker_id": task["worker_id"],
        "run_id": "pid-123",
        "status": "SUCCESS",
        "artifacts": [
            {"path": "bounded.txt", "sha256": hashlib.sha256(b"bounded\\n").hexdigest()}
        ],
        "runtime_identity": task.get("server_binding", "MAC-01")
    }
    ident = dict(base)
    base["result_id"] = "result-" + _canonical_hash(ident)
    return base
""")
        continue
    
    if in_durable:
        if line.startswith("def ") or line.startswith("@pytest"):
            in_durable = False
        else:
            continue
            
    if not in_durable:
        if line.strip() == '"artifacts": result["artifacts"],':
            new_lines.append(line)
            new_lines.append('        "received_runtime_identity": task.get("server_binding", "MAC-01"),\n')
        else:
            new_lines.append(line)

with open("tests/test_server_integration_contract.py", "w") as f:
    f.writelines(new_lines)
