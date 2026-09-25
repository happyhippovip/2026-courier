with open("scripts/mac_adapter.py", "r") as f:
    content = f.read()

content = content.replace("import fcntl\n", "")

replacement = """        with (self.state_dir / "supervisor.lock").open("a") as lock:
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (BlockingIOError, OSError):
                return {"started": False, "reason": "supervisor_active"}"""

import re
content = re.sub(r'        with \(self\.state_dir / "supervisor\.lock"\)\.open\("a"\) as lock:\n            try:\n                fcntl\.flock\(lock, fcntl\.LOCK_EX \| fcntl\.LOCK_NB\)\n            except BlockingIOError:\n                return \{"started": False, "reason": "supervisor_active"\}', replacement, content)

with open("scripts/mac_adapter.py", "w") as f:
    f.write(content)
