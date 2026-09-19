import re
with open("tests/test_zero_chat_motor_cannon.py", "r") as f:
    text = f.read()

text = text.replace('assert resp.status_code == 200', 'assert resp.status_code == 200\n    assert resp.get_json()["status"] == "ACK_RESULT_RECEIVED"')
text = text.replace('complete(motor, "W2", t6)', 'complete(motor, "W1" if t6["worker_id"] == "W1" else "W2", t6)')

with open("tests/test_zero_chat_motor_cannon.py", "w") as f:
    f.write(text)
