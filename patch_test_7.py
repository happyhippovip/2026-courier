with open("tests/test_courier_continue.py", "r") as f:
    code = f.read()

code = code.replace(
    '"validity":"VALID"',
    '"validity":"VALID","producer_id":"test","verifier_id":"test","result_sha256":"0000000000000000000000000000000000000000"'
)

with open("tests/test_courier_continue.py", "w") as f:
    f.write(code)
