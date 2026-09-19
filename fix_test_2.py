import re

with open("tests/test_antigravity_continuous.py", "r") as f:
    code = f.read()

code = code.replace("print('RUNNING SUBPROCESS'); res = subprocess.run([sys.executable, str(script)", "print('RUNNING INIT'); res = subprocess.run([sys.executable, str(script)")
code = code.replace("print('RUNNING SUBPROCESS'); res = subprocess.run([sys.executable, str(runner)", "print('RUNNING RUNNER'); res = subprocess.run([sys.executable, str(runner)")

with open("tests/test_antigravity_continuous.py", "w") as f:
    f.write(code)
