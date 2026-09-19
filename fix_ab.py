with open("tests/test_ab_reconcile_unlock.py", "r") as f:
    code = f.read()

code = code.replace(
    '"received_runtime_identity": task["server_binding"],\n',
    ''
)

with open("tests/test_ab_reconcile_unlock.py", "w") as f:
    f.write(code)
