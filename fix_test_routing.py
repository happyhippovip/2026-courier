import os, glob

for filename in glob.glob("tests/test_*.py"):
    with open(filename, "r") as f:
        code = f.read()

    # We want to replace `"task_id": ` with `"received_runtime_identity": {"sha": "dummy", "runtime": "dummy"}, "task_id": `
    # ONLY when it's inside a `/tasks/verify` call!
    # But wait, it's easier to just find `"task_id": ` and replace it, but that might break other places!
    # Let's see how many places have `/tasks/verify`
    
    code = code.replace(
        '"task_id": "first"',
        '"received_runtime_identity": claim_res["server_binding"], "task_id": "first"'
    )
    code = code.replace(
        '"task_id": "human-task"',
        '"received_runtime_identity": claim_res["server_binding"], "task_id": "human-task"'
    )
    
    with open(filename, "w") as f:
        f.write(code)

