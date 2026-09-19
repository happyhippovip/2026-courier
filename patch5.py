import re
with open("tests/test_zero_chat_motor_cannon.py", "r") as f:
    text = f.read()

payload_replacement = """        "worker_id": worker_id,
        "task_id": task["task_id"],
        "status": status,
        "artifacts": [],
        "raw_result": {"status": status},
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "execution_ref": task["execution_ref"],
        "goal_id": task["goal_id"],
        "result_id": "res-123",
        "run_id": "run-123"
    }"""

text = re.sub(r'"worker_id": worker_id,.*?"raw_result": {"status": status}\n\s*}', payload_replacement, text, flags=re.DOTALL)
with open("tests/test_zero_chat_motor_cannon.py", "w") as f:
    f.write(text)
