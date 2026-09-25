import json, subprocess

task = {
    "task_id": "sleep-task-test-mac-adapter",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer mac_worker_adapter.py um die Testabdeckung im Schlafmodus zu erhoehen.",
    "dependencies": [],
    "read_scopes": ["mac_worker_adapter.py"],
    "write_scopes": ["tests/test_mac_worker_adapter.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

