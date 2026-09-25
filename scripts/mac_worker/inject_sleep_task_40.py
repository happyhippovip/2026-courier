import json, subprocess

task = {
    "task_id": "sleep-task-test-magazine",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer magazine.py.",
    "dependencies": [],
    "read_scopes": ["scripts/magazine.py"],
    "write_scopes": ["tests/test_magazine.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

