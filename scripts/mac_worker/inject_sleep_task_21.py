import json, subprocess

task = {
    "task_id": "sleep-task-test-revenue-customer-intake",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer revenue_customer_intake.py.",
    "dependencies": [],
    "read_scopes": ["scripts/revenue_customer_intake.py"],
    "write_scopes": ["tests/test_revenue_customer_intake.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

