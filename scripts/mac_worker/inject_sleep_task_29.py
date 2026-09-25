import json, subprocess

task = {
    "task_id": "sleep-task-test-windows-crash-recovery",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer windows_crash_recovery.py.",
    "dependencies": [],
    "read_scopes": ["scripts/windows_crash_recovery.py"],
    "write_scopes": ["tests/test_windows_crash_recovery.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

