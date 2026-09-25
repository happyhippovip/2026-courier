import json, subprocess

task = {
    "task_id": "sleep-task-test-orphan-task-reaper",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer orphan_task_reaper.py.",
    "dependencies": [],
    "read_scopes": ["scripts/orphan_task_reaper.py"],
    "write_scopes": ["tests/test_orphan_task_reaper.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

