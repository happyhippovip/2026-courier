import json, subprocess

task = {
    "task_id": "sleep-task-test-windows-update-manager",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer windows_update_manager.py.",
    "dependencies": [],
    "read_scopes": ["scripts/windows_update_manager.py"],
    "write_scopes": ["tests/test_windows_update_manager.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

