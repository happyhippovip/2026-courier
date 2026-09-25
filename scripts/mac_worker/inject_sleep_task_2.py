import json, subprocess

task = {
    "task_id": "sleep-task-test-worker-contract",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer worker_contract.py.",
    "dependencies": [],
    "read_scopes": ["scripts/worker_contract.py"],
    "write_scopes": ["tests/test_worker_contract.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

