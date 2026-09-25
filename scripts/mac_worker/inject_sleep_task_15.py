import json, subprocess

task = {
    "task_id": "sleep-task-test-agent-session-manager",
    "package_id": "sys-audit",
    "description": "Erstelle fehlende Unit-Tests fuer agent_session_manager.py.",
    "dependencies": [],
    "read_scopes": ["scripts/agent_session_manager.py"],
    "write_scopes": ["tests/test_agent_session_manager.py"],
    "status": "READY"
}

payload = json.dumps(task)
subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

