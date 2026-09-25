import json, subprocess

task = {
    "task_id": "sleep-task-test-windows-repair-mode",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer windows_repair_mode.py.",
    "dependencies": [],
    "read_scopes": ["scripts/windows_repair_mode.py"],
    "write_scopes": ["tests/test_windows_repair_mode.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

