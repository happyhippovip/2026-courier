import json, subprocess

task = {
    "task_id": "sleep-task-test-build-memory-update-proposal",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer build_memory_update_proposal.py.",
    "dependencies": [],
    "read_scopes": ["scripts/build_memory_update_proposal.py"],
    "write_scopes": ["tests/test_build_memory_update_proposal.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

