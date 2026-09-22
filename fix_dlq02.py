with open("tests/test_DLQ02_freshness_bound.py", "r") as f:
    c = f.read()

c = c.replace('{"TASKS_COMPLETED": 2}', '{"TASKS_COMPLETED": 2, "STATUS": "DONE"}')

with open("tests/test_DLQ02_freshness_bound.py", "w") as f:
    f.write(c)

