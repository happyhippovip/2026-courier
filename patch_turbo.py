with open("tests/test_turbo_queue.py", "r") as f:
    content = f.read()

content = content.replace('"result_id": "res_B2",', '"result_id": result_B["result_id"],')

with open("tests/test_turbo_queue.py", "w") as f:
    f.write(content)
