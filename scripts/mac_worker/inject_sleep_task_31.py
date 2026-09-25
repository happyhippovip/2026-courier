import json, subprocess

task = {
    "task_id": "sleep-task-test-submit-goal",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer submit_goal.py.",
    "dependencies": [],
    "read_scopes": ["scripts/submit_goal.py"],
    "write_scopes": ["tests/test_submit_goal.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

