with open("scripts/courier_safety_dispatcher.py", "r") as f:
    text = f.read()

text = text.replace(
    'if k not in ("files", "strategy", "acceptance_criteria", "description", "summary", "payload", "task_hash", "correlation_id", "mission_id", "task_id", "result", "result_data"):',
    'if k not in ("files", "target_files", "strategy", "acceptance_criteria", "description", "summary", "payload", "task_hash", "correlation_id", "mission_id", "task_id", "result", "result_data"):'
)

with open("scripts/courier_safety_dispatcher.py", "w") as f:
    f.write(text)
