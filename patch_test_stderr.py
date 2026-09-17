with open("tests/test_antigravity_continuous.py", "r") as f:
    code = f.read()

code = code.replace("print('safe executable tasks or executions length failed')", "print(f'STDERR WAS: {res.stderr}')")

with open("tests/test_antigravity_continuous.py", "w") as f:
    f.write(code)
