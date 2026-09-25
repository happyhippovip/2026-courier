import re
with open("tests/test_turbo_queue_concurrency.py", "r") as f:
    content = f.read()

content = content.replace('state["res_ids"][tid]', 'next(r["result_id"] for r in state["results"] if r["task_id"] == tid)')
content = content.replace('state["res_ids"]["A"]', 'next(r["result_id"] for r in state["results"] if r["task_id"] == "A")')

with open("tests/test_turbo_queue_concurrency.py", "w") as f:
    f.write(content)
