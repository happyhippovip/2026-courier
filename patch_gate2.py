with open("scripts/courier_safety_dispatcher.py", "r") as f:
    text = f.read()

old_if = 'if k not in ("files", "target_files", "strategy", "acceptance_criteria", "description", "summary", "payload", "task_hash", "correlation_id", "mission_id", "task_id", "result", "result_data"):'
new_if = 'if k not in ("files", "target_files", "changed_files", "strategy", "acceptance_criteria", "description", "summary", "payload", "task_hash", "correlation_id", "mission_id", "task_id", "result", "result_data"):'

text = text.replace(old_if, new_if)

with open("scripts/courier_safety_dispatcher.py", "w") as f:
    f.write(text)
