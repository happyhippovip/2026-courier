import json, subprocess

task = {
    "task_id": "sleep-task-test-revenue-v1-safety-baseline",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer revenue_v1_safety_baseline.py.",
    "dependencies": [],
    "read_scopes": ["scripts/revenue_v1_safety_baseline.py"],
    "write_scopes": ["tests/test_revenue_v1_safety_baseline.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

