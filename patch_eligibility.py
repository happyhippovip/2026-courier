with open("tests/test_motor_eligibility_v1.py", "r") as f:
    c = f.read()

c = c.replace(
    '"verdict": "PASS",',
    '"verdict": "PASS",\n                "received_runtime_identity": claimed.get("server_binding"),'
)

with open("tests/test_motor_eligibility_v1.py", "w") as f:
    f.write(c)
