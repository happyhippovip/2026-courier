import json, subprocess

task = {
    "task_id": "sleep-task-test-customer-status-view",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer customer_status_view.py.",
    "dependencies": [],
    "read_scopes": ["scripts/customer_status_view.py"],
    "write_scopes": ["tests/test_customer_status_view.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

