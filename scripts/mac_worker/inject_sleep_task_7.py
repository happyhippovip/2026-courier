import json, subprocess

task = {
    "task_id": "sleep-task-test-github-dispatcher",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer courier_github_dispatcher.py.",
    "dependencies": [],
    "read_scopes": ["scripts/courier_github_dispatcher.py"],
    "write_scopes": ["tests/test_courier_github_dispatcher.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

