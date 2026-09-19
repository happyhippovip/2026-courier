import re

with open("tests/test_motor_eligibility_v1.py", "r") as f:
    code = f.read()

# Let's fix the verify logic directly. 
# Search for `verified = motor.post("/tasks/verify"` and see where it gets the task
code = code.replace(
    '"received_runtime_identity": "mock-binding"',
    '"received_runtime_identity": task["server_binding"]'
)

with open("tests/test_motor_eligibility_v1.py", "w") as f:
    f.write(code)
