import re
with open("scripts/mac_adapter.py", "r") as f:
    content = f.read()

replacement = """        lock = (self.state_dir / "supervisor.lock").open("a")
        try:
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (BlockingIOError, OSError):
                lock.close()
                return {"started": False, "reason": "supervisor_active"}
            self.motor._load()
            if start is not None:
                art, limit, cooldown, local_fake = start
                mode = "INFINITE" if art == "unendlich" else "FINITE"
                started = self.motor.start(mode=mode, limit=limit,
                                           cooldown=cooldown,
                                           local_fake=local_fake)
                if not started.get("started"):
                    return self._rebind(started)
            return self._rebind(self.motor.supervise(max_cycles, idle_sleep))
        finally:
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
            lock.close()"""

content = re.sub(r'        with \(self\.state_dir / "supervisor\.lock"\)\.open\("a"\) as lock:\n            try:.*?return self\._rebind\(self\.motor\.supervise\(max_cycles, idle_sleep\)\)', replacement, content, flags=re.DOTALL)

with open("scripts/mac_adapter.py", "w") as f:
    f.write(content)
