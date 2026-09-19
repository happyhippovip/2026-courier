import subprocess
import sys
res = subprocess.run(["python3", "-m", "pytest", "tests/test_motor_dlq04_adversarial.py", "-v", "-s"], capture_output=True, text=True)
print("STDOUT:")
print(res.stdout)
print("STDERR:")
print(res.stderr)
