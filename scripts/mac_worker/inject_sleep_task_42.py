import json, subprocess

task = {
    "task_id": "sleep-task-test-build-channel-wf-tasks",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer build_channel_workflow_tasks.py.",
    "dependencies": [],
    "read_scopes": ["scripts/build_channel_workflow_tasks.py"],
    "write_scopes": ["tests/test_build_channel_workflow_tasks.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

