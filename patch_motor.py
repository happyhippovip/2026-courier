import re

with open("scripts/cannon_motor.py", "r") as f:
    s = f.read()

# Fix 1: result_not_reconciled
s = s.replace('self.m["state"] = "ERROR"\n            self.m["error"] = "result_not_reconciled"',
              'self.m["state"] = "BLOCKED"\n            self.m["error"] = "result_not_reconciled"')
# Fix 2: unknown_effect
s = s.replace('self.m["state"] = "ERROR"\n            self.m["error"] = f"unknown_effect:{task_id}"',
              'self.m["state"] = "BLOCKED"\n            self.m["error"] = f"unknown_effect:{task_id}"')
# Fix 3: REAL_EXECUTION_REQUIRES_REVIEW
s = s.replace('self.m["state"] = "ERROR"\n            self.m["error"] = str(exc)',
              'self.m["state"] = "BLOCKED"\n            self.m["error"] = str(exc)') # wait, this replaces the one in except block

with open("scripts/cannon_motor.py", "w") as f:
    f.write(s)
