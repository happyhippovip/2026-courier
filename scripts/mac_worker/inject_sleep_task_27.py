import json, subprocess

task = {
    "task_id": "sleep-task-test-export-data",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer export_data.py.",
    "dependencies": [],
    "read_scopes": ["scripts/export_data.py"],
    "write_scopes": ["tests/test_export_data.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

