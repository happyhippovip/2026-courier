import fcntl
def test():
    import os, tempfile
    lock_file = os.path.join(tempfile.gettempdir(), "test.lock")
    fd = os.open(lock_file, os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        print("Got lock")
        # try again
        fd2 = os.open(lock_file, os.O_RDWR)
        fcntl.flock(fd2, fcntl.LOCK_EX | fcntl.LOCK_NB)
        print("Got lock 2")
    except BlockingIOError:
        print("Failed to get lock 2")
test()
