import json, subprocess

task = {
    "task_id": "sleep-task-test-build-handoff-package",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer build_handoff_package.py.",
    "dependencies": [],
    "read_scopes": ["scripts/build_handoff_package.py"],
    "write_scopes": ["tests/test_build_handoff_package.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

