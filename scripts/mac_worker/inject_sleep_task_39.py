import json, subprocess

task = {
    "task_id": "sleep-task-test-intake-dispatcher",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer intake_dispatcher.py.",
    "dependencies": [],
    "read_scopes": ["scripts/intake_dispatcher.py"],
    "write_scopes": ["tests/test_intake_dispatcher.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

