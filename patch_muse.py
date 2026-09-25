import re
with open("pre_courier_muse/muse_runner.py", "r") as f:
    content = f.read()

content = content.replace("import fcntl\n", "")

replacement = """def acquire_lock(lock_file):
    lock_fd = os.open(lock_file, os.O_RDWR | os.O_CREAT)
    try:
        if sys.platform == 'win32':
            import msvcrt
            msvcrt.locking(lock_fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_fd
    except (BlockingIOError, OSError):
        os.close(lock_fd)
        return None

def release_lock(lock_fd):
    if lock_fd is not None:
        if sys.platform == 'win32':
            import msvcrt
            msvcrt.locking(lock_fd, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)

def is_another_instance_running():
    return acquire_lock(LOCK_FILE)"""

content = re.sub(r'def is_another_instance_running\(\):\n    lock_fd = os\.open\(LOCK_FILE, os\.O_RDWR \| os\.O_CREAT\)\n    try:\n        fcntl\.flock\(lock_fd, fcntl\.LOCK_EX \| fcntl\.LOCK_NB\)\n        return lock_fd\n    except BlockingIOError:\n        return None', replacement, content)

content = content.replace("os.close(lock_fd)", "release_lock(lock_fd)")

with open("pre_courier_muse/muse_runner.py", "w") as f:
    f.write(content)
