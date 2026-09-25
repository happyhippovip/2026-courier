import re
with open("tests/test_turbo_queue_concurrency.py", "r") as f:
    c = f.read()

c = c.replace(
    'state["res_ids"][tid]',
    't_data["result"]["result_id"]'
)
with open("tests/test_turbo_queue_concurrency.py", "w") as f:
    f.write(c)

