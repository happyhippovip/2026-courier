with open("scripts/courier_verifier.py", "r") as f:
    code = f.read()

code = code.replace(
    '"verifier_id": VERIFIER_ID,',
    '"verifier_id": VERIFIER_ID,\n                        "received_runtime_identity": task.get("server_binding"),'
)

with open("scripts/courier_verifier.py", "w") as f:
    f.write(code)
