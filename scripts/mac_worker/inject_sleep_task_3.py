import json, subprocess

task = {
    "task_id": "sleep-task-fix-other-adapters",
    "package_id": "sys-audit",
    "description": "Pruefe github_worker_adapter.py und gemini_worker_adapter.py auf den timeout file_not_found bug und behebe ihn samt Tests.",
    "dependencies": [],
    "read_scopes": ["scripts/github_worker_adapter.py", "scripts/gemini_worker_adapter.py"],
    "write_scopes": ["scripts/github_worker_adapter.py", "scripts/gemini_worker_adapter.py", "tests/test_github_worker_adapter.py", "tests/test_gemini_worker_adapter.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

