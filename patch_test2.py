with open("tests/test_antigravity_continuous.py", "r") as f:
    code = f.read()

code = code.replace("assert len(executions) >= 3", "print('safe executable tasks or executions length failed')\n        assert len(executions) >= 3")

with open("tests/test_antigravity_continuous.py", "w") as f:
    f.write(code)
