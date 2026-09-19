with open("tests/test_antigravity_continuous.py", "r") as f:
    code = f.read()

code = code.replace(
    '"runtime_binding":"test"',
    '"runtime_binding":"0000000000000000000000000000000000000000"'
)

with open("tests/test_antigravity_continuous.py", "w") as f:
    f.write(code)
