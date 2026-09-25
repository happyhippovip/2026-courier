import re

with open("scripts/cannon_motor.py", "r") as f:
    content = f.read()

# Replace definition
content = re.sub(
    r"def deterministic_executor\(results_dir, task_id, behavior=\"ok\"\):",
    "def deterministic_executor(results_dir, task, behavior=\"ok\"):",
    content
)

# In the body, we need to extract task_id and compute result_id
replacement = """    task_id = task['task_id']
    if behavior == "crash":
        raise MotorError(f"executor crash on {task_id}")
    import hashlib
    identity = {
        'task_id': task_id,
        'attempt_id': task.get('attempt_id'),
        'dispatch_id': task.get('dispatch_id'),
        'executor_kind': 'LOCAL_FAKE'
    }
    payload_str = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    result_id = "result-" + hashlib.sha256(payload_str).hexdigest()"""

content = re.sub(
    r"    if behavior == \"crash\":\n        raise MotorError\(f\"executor crash on \{task_id\}\"\)\n    result_id = f\"\{task_id\}:r1\"",
    replacement,
    content
)

# And replace the call
content = re.sub(
    r"outcome, result_id = deterministic_executor\(self.results_dir, task_id, behavior\)",
    "outcome, result_id = deterministic_executor(self.results_dir, task, behavior)",
    content
)

with open("scripts/cannon_motor.py", "w") as f:
    f.write(content)
