import json, subprocess

task = {
    "task_id": "sleep-task-test-update-courier",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer update_courier.py und repariere Header.",
    "dependencies": [],
    "read_scopes": ["scripts/update_courier.py"],
    "write_scopes": ["tests/test_update_courier.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

