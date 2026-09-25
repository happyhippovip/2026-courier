import json, subprocess

task = {
    "task_id": "sleep-task-test-scope-ledger",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer scope_ledger.py.",
    "dependencies": [],
    "read_scopes": ["scripts/scope_ledger.py"],
    "write_scopes": ["tests/test_scope_ledger.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

