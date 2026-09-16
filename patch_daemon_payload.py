import os, uuid
with open("scripts/mac_worker/daemon.py", "r") as f:
    c = f.read()

c = c.replace('"task_id": tid,', '"""task_id": tid,\n                "dispatch_id": task.get("dispatch_id"),\n                "attempt_id": task.get("attempt_id"),\n                "run_id": str(uuid.uuid4()),\n                "result_id": str(uuid.uuid4()),"""')
c = c.replace('"""task_id"', '"task_id"')
c = c.replace('""")', '')

with open("scripts/mac_worker/daemon.py", "w") as f:
    f.write(c)

