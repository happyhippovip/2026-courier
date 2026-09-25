import json, subprocess

task = {
    "task_id": "sleep-task-test-queue-processor",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer queue_processor.py.",
    "dependencies": [],
    "read_scopes": ["scripts/queue_processor.py"],
    "write_scopes": ["tests/test_queue_processor.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

