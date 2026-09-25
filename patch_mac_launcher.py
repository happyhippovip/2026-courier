with open("app/cannon/mac_launcher.py", "r") as f:
    content = f.read()

content = content.replace("import fcntl\n", "")

replacement = """        while True:
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (BlockingIOError, OSError):"""

import re
content = re.sub(r'        while True:\n            try:\n                fcntl\.flock\(lock, fcntl\.LOCK_EX \| fcntl\.LOCK_NB\)\n                break\n            except BlockingIOError:', replacement, content)

with open("app/cannon/mac_launcher.py", "w") as f:
    f.write(content)
