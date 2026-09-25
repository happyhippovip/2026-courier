import json, subprocess

task = {
    "task_id": "sleep-task-test-task-routing",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer task_routing.py.",
    "dependencies": [],
    "read_scopes": ["scripts/task_routing.py"],
    "write_scopes": ["tests/test_task_routing.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

