import json, subprocess

task = {
    "task_id": "sleep-task-test-support-bundle",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer support_bundle.py.",
    "dependencies": [],
    "read_scopes": ["scripts/support_bundle.py"],
    "write_scopes": ["tests/test_support_bundle.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

