import os
with open("scripts/revenue_worker_adapter.py", "r") as f:
    c = f.read()

lock_code = """
import fcntl
def acquire_single_instance_lock():
    lock_file = STATE_DIR / "revenue_daemon.lock"
    lock_fd = open(lock_file, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_fd
    except BlockingIOError:
        print("Another instance of revenue worker is already running. Exiting.")
        sys.exit(0)
"""

if "acquire_single_instance_lock" not in c:
    c = c.replace("def main():", lock_code + "\ndef main():\n    _lock_fd = acquire_single_instance_lock()\n")

with open("scripts/revenue_worker_adapter.py", "w") as f:
    f.write(c)
