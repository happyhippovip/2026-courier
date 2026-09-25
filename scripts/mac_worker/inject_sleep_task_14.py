import json, subprocess

task = {
    "task_id": "sleep-task-test-apply-ledger-patch",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer apply_ledger_patch.py.",
    "dependencies": [],
    "read_scopes": ["scripts/apply_ledger_patch.py"],
    "write_scopes": ["tests/test_apply_ledger_patch.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

