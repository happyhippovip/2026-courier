import json, subprocess

task = {
    "task_id": "sleep-task-test-stack-inspector",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer stack_inspector.py.",
    "dependencies": [],
    "read_scopes": ["scripts/stack_inspector.py"],
    "write_scopes": ["tests/test_stack_inspector.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

