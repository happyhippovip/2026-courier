import re
with open("tests/test_zero_chat_motor_cannon.py", "r") as f:
    text = f.read()

text = text.replace('    assert resp.get_json()["status"] == "ACK_RESULT_RECEIVED"\n', '')

text = text.replace('resp = http.post("/tasks/result", headers=auth(), json=payload)\n    assert resp.status_code == 200', 'resp = http.post("/tasks/result", headers=auth(), json=payload)\n    assert resp.status_code == 200\n    assert resp.get_json()["status"] == "ACK_RESULT_RECEIVED"')

with open("tests/test_zero_chat_motor_cannon.py", "w") as f:
    f.write(text)
