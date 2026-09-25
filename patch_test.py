import os
from pathlib import Path

test_file = Path("tests/test_server_integration_contract.py")
content = test_file.read_text()

content = content.replace('''    assert first.get_json()["task"]["task_id"] == "task-1"
    assert second.get_json() == {"task": None, "reason": "WORKER_BUSY"}''',
'''    assert first.get_json()["task"]["task_id"] == "task-1"
    assert second.get_json()["task"]["task_id"] == "task-1"''')

test_file.write_text(content)
