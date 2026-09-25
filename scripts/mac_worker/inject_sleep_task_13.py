import json, subprocess

task = {
    "task_id": "sleep-task-test-resource-policy",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer resource_policy.py.",
    "dependencies": [],
    "read_scopes": ["scripts/resource_policy.py"],
    "write_scopes": ["tests/test_resource_policy.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

