import json, subprocess

task = {
    "task_id": "sleep-task-test-validate-courier-task",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer validate_courier_task.py.",
    "dependencies": [],
    "read_scopes": ["scripts/validate_courier_task.py"],
    "write_scopes": ["tests/test_validate_courier_task.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

