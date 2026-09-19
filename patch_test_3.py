with open("tests/test_antigravity_continuous.py", "r") as f:
    code = f.read()

code = code.replace(
    '"validity": "UNKNOWN"',
    '"validity": "VALID",\n            "producer_id": "test",\n            "verifier_id": "test",\n            "result_sha256": "0000000000000000000000000000000000000000"'
)

with open("tests/test_antigravity_continuous.py", "w") as f:
    f.write(code)
