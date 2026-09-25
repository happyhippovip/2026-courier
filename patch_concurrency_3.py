import re
with open("tests/test_turbo_queue_concurrency.py", "r") as f:
    c = f.read()

c = c.replace(
    'state["res_ids"]["A"]',
    'state["tasks"]["A"]["result"]["result_id"]'
)
with open("tests/test_turbo_queue_concurrency.py", "w") as f:
    f.write(c)

