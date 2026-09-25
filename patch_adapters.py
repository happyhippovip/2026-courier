import re

with open("app/cannon/adapters.py", "r") as f:
    content = f.read()

replacement = """        identity = {'executor_kind': 'REAL_MUSE', 'provider': 'meta', 'task_id': task['task_id'],
                    'attempt_id': task.get('attempt_id'), 'dispatch_id': task.get('dispatch_id'),
                    'execution_id': execution, 'worker_id': 'muse-' + execution,
                    'started_at': time.time(), 'heartbeat_at': time.time(), 'terminal': False}"""

content = re.sub(
    r"        identity = \{'executor_kind': 'REAL_MUSE', 'provider': 'meta', 'task_id': task\['task_id'\],\n                    'execution_id': execution, 'worker_id': 'muse-' \+ execution,\n                    'started_at': time.time\(\), 'heartbeat_at': time.time\(\), 'terminal': False\}",
    replacement,
    content,
    flags=re.MULTILINE
)

with open("app/cannon/adapters.py", "w") as f:
    f.write(content)
