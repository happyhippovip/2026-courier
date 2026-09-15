import sys
with open('scripts/courier_real_worker_adapters.py', 'r') as f:
    code = f.read()

old_check = 'if "SUCCESS: Result fetched successfully." in res.stdout and ("EXIT_CODE: 0" in res.stdout or "EXIT_CODE: None" in res.stdout):'
new_check = 'if "SUCCESS: Result fetched successfully." in res.stdout and "EXIT_CODE: 0" in res.stdout and "STATUS: SUCCESS" in res.stdout:'
code = code.replace(old_check, new_check)

with open('scripts/courier_real_worker_adapters.py', 'w') as f:
    f.write(code)
