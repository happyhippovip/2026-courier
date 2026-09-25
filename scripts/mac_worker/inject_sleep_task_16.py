import json, subprocess

task = {
    "task_id": "sleep-task-test-cleanup-handler",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer cleanup_handler.py.",
    "dependencies": [],
    "read_scopes": ["scripts/cleanup_handler.py"],
    "write_scopes": ["tests/test_cleanup_handler.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

