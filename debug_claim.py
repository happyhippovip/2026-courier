import re

with open("server/app.py", "r") as f:
    c = f.read()

debug = """
    print(f"[DEBUG claim_task] worker_id={worker_id}, lock_key={lock_key}, lock_time={state.get('provider_locks', {}).get(lock_key, 0)}, time={time.time()}", flush=True)
    
    for task_id, task in state.get("tasks", {}).items():
"""
c = re.sub(
    r'    for task_id, task in state\.get\("tasks", \{\}\)\.items\(\):',
    debug.strip('\n'),
    c,
    flags=re.DOTALL
)

debug2 = """
                if not _worker_is_eligible(state, candidate, worker_id):
                    print(f"[DEBUG claim_task] Worker {worker_id} NOT eligible for {candidate['task_id']}", flush=True)
                    continue
"""
c = re.sub(
    r'                if not _worker_is_eligible\(state, candidate, worker_id\):\n                    continue',
    debug2.strip('\n'),
    c,
    flags=re.DOTALL
)

with open("server/app.py", "w") as f:
    f.write(c)

