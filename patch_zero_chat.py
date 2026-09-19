with open("tests/test_zero_chat_motor_cannon.py", "r") as f:
    code = f.read()

# Change def verify
code = code.replace(
    'def verify(http, task_id):',
    'def verify(http, task):'
)
code = code.replace(
    '{"task_id": task_id, "verdict": "PASS", "received_runtime_identity": "test", "verifier_id": "V1", "result_id": f"res-{task_id}", "artifacts": []}',
    '{"task_id": task["task_id"], "verdict": "PASS", "received_runtime_identity": task["server_binding"], "verifier_id": "V1", "result_id": f"res-{task[\'task_id\']}", "artifacts": []}'
)

# Replace calls
code = code.replace('verify(motor, "A")', 'verify(motor, a_task)')
code = code.replace('verify(motor, "B")', 'verify(motor, t3)')
code = code.replace('verify(motor, "C")', 'verify(motor, c_task)')
code = code.replace('verify(motor, "D")', 'verify(motor, t4)')
code = code.replace('verify(motor, "E")', 'verify(motor, t5)')
code = code.replace('verify(motor, f"T{i}")', 'verify(motor, t)')

with open("tests/test_zero_chat_motor_cannon.py", "w") as f:
    f.write(code)
