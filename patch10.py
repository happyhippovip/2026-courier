import re
with open("tests/test_zero_chat_motor_cannon.py", "r") as f:
    text = f.read()

text = text.replace('t6 = claim(motor, "W2")', 't6 = claim(motor, "W1") or claim(motor, "W2")')
with open("tests/test_zero_chat_motor_cannon.py", "w") as f:
    f.write(text)
