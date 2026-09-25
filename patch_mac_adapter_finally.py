import re
with open("scripts/mac_adapter.py", "r") as f:
    content = f.read()

replacement = """        finally:
            if not lock.closed:
                try:
                    if os.name == 'nt':
                        import msvcrt
                        msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
                lock.close()"""

content = re.sub(r'        finally:\n            try:\n                if os\.name == \'nt\':\n                    import msvcrt\n                    msvcrt\.locking\(lock\.fileno\(\), msvcrt\.LK_UNLCK, 1\)\n            except OSError:\n                pass\n            lock\.close\(\)', replacement, content)

with open("scripts/mac_adapter.py", "w") as f:
    f.write(content)
