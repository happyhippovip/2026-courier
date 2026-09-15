from pathlib import Path

p = Path("scripts/courier_real_worker_adapters.py")
code = p.read_text()

old = '''            if "SUCCESS: Result fetched successfully." in res.stdout and "EXIT_CODE: 0" in res.stdout:'''
new = '''            if "SUCCESS: Result fetched successfully." in res.stdout and ("EXIT_CODE: 0" in res.stdout or "EXIT_CODE: None" in res.stdout):'''

code = code.replace(old, new)
p.write_text(code)
print("Patched success condition.")
