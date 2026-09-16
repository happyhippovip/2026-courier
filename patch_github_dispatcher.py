import os
with open("scripts/courier_github_dispatcher.py", "r") as f:
    c = f.read()

lock_code = """
import fcntl
def acquire_single_instance_lock():
    lock_file = "/tmp/courier_github_dispatcher.lock"
    lock_fd = open(lock_file, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_fd
    except BlockingIOError:
        print("Another instance of github dispatcher is already running. Exiting.")
        sys.exit(0)
"""

if "acquire_single_instance_lock" not in c:
    c = c.replace("def run_loop():", lock_code + "\ndef run_loop():\n    _lock_fd = acquire_single_instance_lock()\n")

with open("scripts/courier_github_dispatcher.py", "w") as f:
    f.write(c)
