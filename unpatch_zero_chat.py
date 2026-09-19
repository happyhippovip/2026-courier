with open("tests/test_zero_chat_motor_cannon.py", "r") as f:
    code = f.read()

code = code.replace('verify(motor, c_task)', 'verify(motor, t4)')
code = code.replace('verify(motor, t4)', 'verify(motor, t4)') # Already t4?
# Let's just fix it manually.
