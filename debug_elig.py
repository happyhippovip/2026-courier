import re

with open("server/app.py", "r") as f:
    c = f.read()

debug = """
    if time.time() <= state.get("provider_locks", {}).get(lock_key, 0):
        if task.get("mode") != "NATIVE":
            print(f"[DEBUG _worker_is_eligible] Worker {worker_id} blocked by provider lock for {task.get('task_id')}", flush=True)
            return False
        else:
            print(f"[DEBUG _worker_is_eligible] Worker {worker_id} bypassed provider lock for NATIVE {task.get('task_id')}", flush=True)
            
    if _task_requires_human_gate(task):
"""
c = re.sub(
    r'    if time\.time\(\) <= state\.get\("provider_locks", \{\}\)\.get\(lock_key, 0\):\n        if task\.get\("mode"\) != "NATIVE":\n            return False\n\n    if _task_requires_human_gate\(task\):',
    debug.strip('\n'),
    c,
    flags=re.DOTALL
)

with open("server/app.py", "w") as f:
    f.write(c)

