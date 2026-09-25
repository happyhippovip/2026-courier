import json, subprocess

task = {
    "task_id": "sleep-task-test-build-ag-worker-job",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer build_antigravity_worker_job.py.",
    "dependencies": [],
    "read_scopes": ["scripts/build_antigravity_worker_job.py"],
    "write_scopes": ["tests/test_build_antigravity_worker_job.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

