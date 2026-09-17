with open("tests/test_antigravity_continuous.py", "r") as f:
    code = f.read()

code = code.replace("res = subprocess.run([sys.executable, str(runner), \"--run\", \"--once\"], env=env, capture_output=True, text=True)", "res = subprocess.run([sys.executable, str(runner), \"--run\", \"--once\"], env=env, capture_output=True, text=True, errors='replace')")
code = code.replace("res.stdout.decode('utf-8', errors='replace')", "res.stdout")
code = code.replace("b\"Prove edge: PILOT INTAKE\"", "\"Prove edge: PILOT INTAKE\"")
code = code.replace("b\"Prove edge: SALES PACKAGE\"", "\"Prove edge: SALES PACKAGE\"")
code = code.replace("assert len(executions) >= 3", "print('STDOUT:', res.stdout)\\n    print('STDERR:', res.stderr)\\n    assert len(executions) >= 3")

with open("tests/test_antigravity_continuous.py", "w") as f:
    f.write(code)
