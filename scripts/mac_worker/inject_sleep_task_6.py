import json, subprocess

task = {
    "task_id": "sleep-task-fix-content-production-todo",
    "package_id": "sys-audit",
    "description": "Ersetze das TODO in run_content_production_pipeline.py durch den korrekten Aufruf von publish_youtube_package.py.",
    "dependencies": [],
    "read_scopes": ["scripts/run_content_production_pipeline.py"],
    "write_scopes": ["scripts/run_content_production_pipeline.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

