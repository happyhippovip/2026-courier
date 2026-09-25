import subprocess
import os

try:
    print("Running pytest tests/test_windows_runtime_torture.py -s")
    proc = subprocess.run(["pytest", "tests/test_windows_runtime_torture.py", "-s"], capture_output=True, text=True)
    print(proc.stdout)
    print(proc.stderr)
except Exception as e:
    print(e)
