import re
with open("tests/test_motor_eligibility_v1.py", "r") as f:
    c = f.read()

c = c.replace('assert verified.get_json()["status"] == "RECONCILED"', 'assert verified.get_json().get("status") == "RECONCILED", verified.get_json()')
c = c.replace('assert verified.get_json()["status"] == "RECONCILED_PENDING_MERGE"', 'assert verified.get_json().get("status") == "RECONCILED_PENDING_MERGE", verified.get_json()')

with open("tests/test_motor_eligibility_v1.py", "w") as f:
    f.write(c)

