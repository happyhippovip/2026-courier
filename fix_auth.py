with open("scripts/courier_safety_dispatcher.py", "r") as f:
    content = f.read()

content = content.replace(
    'if k not in ("context", "files", "strategy", "acceptance_criteria", "description", "summary", "payload"):',
    'if k not in ("context", "files", "strategy", "acceptance_criteria", "description", "summary", "payload", "task_hash", "correlation_id", "mission_id", "task_id", "result", "result_data"):'
)

with open("scripts/courier_safety_dispatcher.py", "w") as f:
    f.write(content)
