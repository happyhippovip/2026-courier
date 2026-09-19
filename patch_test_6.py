with open("tests/test_antigravity_continuous.py", "r") as f:
    code = f.read()

code = code.replace(
    'capture_output=False',
    'capture_output=True, text=True, errors=\'replace\''
)

with open("tests/test_antigravity_continuous.py", "w") as f:
    f.write(code)
