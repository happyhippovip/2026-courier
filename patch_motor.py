import re
with open("tests/test_motor_eligibility_v1.py", "r") as f:
    content = f.read()

content = content.replace('assert verified.get_json()["status"] == "RECONCILED"', 'print("DEBUG", verified.get_json())\n    assert verified.get_json()["status"] == "RECONCILED"')

with open("tests/test_motor_eligibility_v1.py", "w") as f:
    f.write(content)
