import json, subprocess

task = {
    "task_id": "sleep-task-test-invoice-generator",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer invoice_generator.py.",
    "dependencies": [],
    "read_scopes": ["scripts/invoice_generator.py"],
    "write_scopes": ["tests/test_invoice_generator.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

