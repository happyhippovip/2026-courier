import re

with open("scripts/cannon_motor.py", "r") as f:
    s = f.read()

s = re.sub(r'self\.m\["state"\] = "ERROR"\s+self\.m\["error"\] = "result_not_reconciled"',
           'self.m["state"] = "BLOCKED"\\n            self.m["error"] = "result_not_reconciled"', s)

s = re.sub(r'self\.m\["state"\] = "ERROR"\s+self\.m\["error"\] = f"unknown_effect:\{task_id\}"',
           'self.m["state"] = "BLOCKED"\\n            self.m["error"] = f"unknown_effect:{task_id}"', s)

s = re.sub(r'self\.m\["needs_review"\].append\(task_id\)\s+self\.m\["state"\] = "ERROR"\s+self\.m\["error"\] = str\(exc\)',
           'self.m["needs_review"].append(task_id)\\n            self.m["state"] = "BLOCKED"\\n            self.m["error"] = str(exc)', s)

s = re.sub(r'return \{"step": "unknown_halt", "task": task_id,\s+"state": "ERROR"\}',
           'return {"step": "unknown_halt", "task": task_id,\\n                    "state": "BLOCKED"}', s)

with open("scripts/cannon_motor.py", "w") as f:
    f.write(s)
