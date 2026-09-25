import json, subprocess

task = {
    "task_id": "sleep-task-test-rc-builder",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer rc_builder.py.",
    "dependencies": [],
    "read_scopes": ["scripts/rc_builder.py"],
    "write_scopes": ["tests/test_rc_builder.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

