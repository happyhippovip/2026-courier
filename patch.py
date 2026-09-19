import re
with open('app/cannon/web.py', 'r') as f:
    content = f.read()

# Fix 1: Error propagation
content = content.replace("'error': None,", "'error': mac.get('error'),")

# Fix 2: Stranded RUNNING -> READY
old_st = "elif is_active: st = 'RUNNING'"
new_st = "elif is_active:\n            if not helper_active:\n                st = 'ERROR' if CHILD is not None and CHILD.poll() not in (0, None) else 'READY'\n            else:\n                st = 'RUNNING'\n        elif st == 'BLOCKED': st = 'BLOCKED'"
content = content.replace(old_st, new_st)

# Fix 3: Limit mode to BEGRENZT
content = content.replace("if mode not in {'BEGRENZT', 'UNENDLICH'}:", "if mode not in {'BEGRENZT'}:")

with open('app/cannon/web.py', 'w') as f:
    f.write(content)
