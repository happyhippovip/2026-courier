import json, subprocess

task = {
    "task_id": "sleep-task-test-sync-ledger",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer sync_ledger.py.",
    "dependencies": [],
    "read_scopes": ["scripts/sync_ledger.py"],
    "write_scopes": ["tests/test_sync_ledger.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

