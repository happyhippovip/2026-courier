import json, subprocess

task = {
    "task_id": "sleep-task-test-entitlement-boundary",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer entitlement_boundary.py.",
    "dependencies": [],
    "read_scopes": ["scripts/entitlement_boundary.py"],
    "write_scopes": ["tests/test_entitlement_boundary.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

