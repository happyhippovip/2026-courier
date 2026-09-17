with open("tests/test_antigravity_continuous.py", "r") as f:
    code = f.read()
code = code.replace("print('STDOUT:', res.stdout)\\n    print('STDERR:', res.stderr)\\n    assert len(executions) >= 3", "print('STDOUT:', res.stdout)\n    print('STDERR:', res.stderr)\n    assert len(executions) >= 3")
with open("tests/test_antigravity_continuous.py", "w") as f:
    f.write(code)
