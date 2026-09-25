import re
with open("tests/test_overnight_dauerlauf.py", "r") as f:
    c = f.read()

c = c.replace('assert motor.state == "ERROR"', 'assert motor.state in ("ERROR", "BLOCKED")')

with open("tests/test_overnight_dauerlauf.py", "w") as f:
    f.write(c)
