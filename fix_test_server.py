import pathlib
p = pathlib.Path('tests/test_server_integration_contract.py')
t = p.read_text('utf-8')

old = '''    result = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "run_id": "pid-123",
        "status": "SUCCESS",'''

new = '''    import time
    result = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "run_id": "pid-123",
        "status": "SUCCESS",
        "execution_start_at": time.time(),
        "execution_end_at": time.time(),'''

if old in t:
    p.write_text(t.replace(old, new), 'utf-8')
    print('replaced')
else:
    print('not found')
