import re
with open("app/cannon/mac_launcher.py", "r") as f:
    content = f.read()

replacement = """    directory = Path.home() / ".courier"
    directory.mkdir(exist_ok=True)
    lock = (directory / "cannon-launch.lock").open("a")
    try:
        deadline = time.monotonic() + 12
        while True:
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (BlockingIOError, OSError):
                if time.monotonic() >= deadline:
                    raise RuntimeError("Another Cannon launch has not finished")
                time.sleep(0.1)
        return open_cannon()
    finally:
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        lock.close()"""

content = re.sub(r'    directory = Path\.home\(\) / "\.courier"\n    directory\.mkdir\(exist_ok=True\)\n    with \(directory / "cannon-launch\.lock"\)\.open\("a"\) as lock:\n.*?return open_cannon\(\)', replacement, content, flags=re.DOTALL)

with open("app/cannon/mac_launcher.py", "w") as f:
    f.write(content)
