import json, subprocess

task = {
    "task_id": "sleep-task-test-product-health-check",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer product_health_check.py.",
    "dependencies": [],
    "read_scopes": ["scripts/product_health_check.py"],
    "write_scopes": ["tests/test_product_health_check.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

