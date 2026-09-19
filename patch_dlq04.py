with open("tests/test_motor_dlq04_adversarial.py", "r") as f:
    code = f.read()

code = code.replace('"validity":"VALID"', '"validity":"VALID","producer_id":"producer_1","verifier_id":"verifier_1","result_sha256":"0000000000000000000000000000000000000000"')

with open("tests/test_motor_dlq04_adversarial.py", "w") as f:
    f.write(code)

