import re
with open("tests/test_turbo_queue_concurrency.py", "r") as f:
    content = f.read()

content = content.replace('state = server.app.load_state()\n', 'state = server.app.load_state()\n    res_ids = {r["task_id"]: r["result_id"] for r in state.get("results", [])}\n')
content = content.replace('state["res_ids"]', 'res_ids')

with open("tests/test_turbo_queue_concurrency.py", "w") as f:
    f.write(content)
