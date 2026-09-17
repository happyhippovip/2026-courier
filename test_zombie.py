import subprocess
import time
import os
import signal

process = subprocess.Popen(["sleep", "10"], start_new_session=True)
try:
    stdout, stderr = process.communicate(timeout=1)
except subprocess.TimeoutExpired:
    pgid = os.getpgid(process.pid)
    os.killpg(pgid, signal.SIGKILL)

# Do not call wait. Let's see if it's a zombie.
time.sleep(2)
subprocess.run(["ps", "-o", "pid,stat,command"])
