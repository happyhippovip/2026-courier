with open("tests/test_motor_dlq04_adversarial.py", "r") as f:
    code = f.read()

code = code.replace('"TEST-GOAL"', '"test-goal"')

with open("tests/test_motor_dlq04_adversarial.py", "w") as f:
    f.write(code)
