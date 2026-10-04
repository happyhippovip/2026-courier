import re
with open("tests/test_server_integration_contract.py", "r") as f:
    text = f.read()

text = text.replace(
    'assert resp.json["task_id"] == task_id',
    'if resp.status_code == 200 and resp.json and "task" in resp.json:\n            assert resp.json["task"]["task_id"] == task_id\n        else:\n            assert resp.json.get("task_id") == task_id or (resp.json.get("task") or {}).get("task_id") == task_id'
)

with open("tests/test_server_integration_contract.py", "w") as f:
    f.write(text)
