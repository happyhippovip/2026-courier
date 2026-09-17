import re

with open("scripts/mac_worker/daemon.py", "r") as f:
    code = f.read()

code = code.replace("os.killpg(pgid, signal.SIGKILL)", "os.killpg(pgid, signal.SIGKILL)\n                    process.wait(timeout=2)")
code = code.replace("process.kill()", "process.kill()\n                    process.wait(timeout=2)")

with open("scripts/mac_worker/daemon.py", "w") as f:
    f.write(code)
