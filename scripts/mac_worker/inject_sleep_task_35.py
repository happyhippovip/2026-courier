import json, subprocess

task = {
    "task_id": "sleep-task-test-safe-repair",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer safe_repair.py.",
    "dependencies": [],
    "read_scopes": ["scripts/safe_repair.py"],
    "write_scopes": ["tests/test_safe_repair.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

