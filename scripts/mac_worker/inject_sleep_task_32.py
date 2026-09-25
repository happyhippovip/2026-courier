import json, subprocess

task = {
    "task_id": "sleep-task-test-publish-courier-result",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer publish_courier_result.py.",
    "dependencies": [],
    "read_scopes": ["scripts/publish_courier_result.py"],
    "write_scopes": ["tests/test_publish_courier_result.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

