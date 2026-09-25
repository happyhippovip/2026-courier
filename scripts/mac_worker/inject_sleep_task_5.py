import json, subprocess

task = {
    "task_id": "sleep-task-test-courier-verifier",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer courier_verifier.py, um die Verifier-Logik robuster zu machen.",
    "dependencies": [],
    "read_scopes": ["scripts/courier_verifier.py"],
    "write_scopes": ["tests/test_courier_verifier.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

