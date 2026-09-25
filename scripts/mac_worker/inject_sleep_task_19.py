import json, subprocess

task = {
    "task_id": "sleep-task-test-human-gate-ux",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer human_gate_ux.py.",
    "dependencies": [],
    "read_scopes": ["scripts/human_gate_ux.py"],
    "write_scopes": ["tests/test_human_gate_ux.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

