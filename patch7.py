import re
with open("tests/test_zero_chat_motor_cannon.py", "r") as f:
    text = f.read()

text = text.replace('"res-123"', 'f"res-{task[\'task_id\']}"')
text = text.replace('def verify(http, task_id):', 'def verify(http, task_id):\n    result_id = f"res-{task_id}"')
text = text.replace('"verdict": "PASS", "verifier_id": "V1"', '"verdict": "PASS", "verifier_id": "V1", "result_id": result_id')

with open("tests/test_zero_chat_motor_cannon.py", "w") as f:
    f.write(text)
