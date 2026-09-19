import re
with open("tests/test_zero_chat_motor_cannon.py", "r") as f:
    text = f.read()

text = re.sub(r'goal = motor.get.*/goals.*', 'print("GOALS:", motor.get("/goals", headers=auth()).get_json(), flush=True)', text)
with open("tests/test_zero_chat_motor_cannon.py", "w") as f:
    f.write(text)
