import json, subprocess

task = {
    "task_id": "sleep-task-analyze-dead-scripts",
    "package_id": "sys-audit",
    "description": "Analysiere patch_tomato_test_*.py und patch_retries.py auf toten Code und bereite ein Arbeitspaket zur Bereinigung vor.",
    "dependencies": [],
    "read_scopes": ["patch_tomato_test.py", "patch_retries.py"],
    "write_scopes": ["artifacts/dead_code_cleanup_plan.md"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

