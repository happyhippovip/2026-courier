import os, glob

for filename in glob.glob("tests/test_*.py"):
    with open(filename, "r") as f:
        code = f.read()

    code = code.replace(
        '"task_id": "terminal"',
        '"received_runtime_identity": claim_res["server_binding"], "task_id": "terminal"'
    )
    code = code.replace(
        '"task_id": "protected"',
        '"received_runtime_identity": claim_res["server_binding"], "task_id": "protected"'
    )

    with open(filename, "w") as f:
        f.write(code)

