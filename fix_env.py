import re

with open("tests/test_antigravity_continuous.py", "r") as f:
    code = f.read()

code = code.replace(
    'env["MOCK_SHA"] = "0000000000000000000000000000000000000000"',
    'env["MOCK_SHA"] = "0000000000000000000000000000000000000000"\n    env["MOCK_LEDGER"] = "1"'
)

with open("tests/test_antigravity_continuous.py", "w") as f:
    f.write(code)
