import json, subprocess

task = {
    "task_id": "sleep-task-test-log-rotation",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer log_rotation.py.",
    "dependencies": [],
    "read_scopes": ["scripts/log_rotation.py"],
    "write_scopes": ["tests/test_log_rotation.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

