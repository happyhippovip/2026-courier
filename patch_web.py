import re

with open("app/cannon/web.py", "r") as f:
    s = f.read()

# Fix 1: Properly pass through error
s = s.replace("'error': None,", "'error': mac.get('error') or (CHILD.poll() if CHILD is not None else None),")

# Fix 2: Stranded RUNNING -> READY
old_st = """        elif is_active: st = 'RUNNING'"""
new_st = """        elif is_active:
            if not helper_active:
                st = 'READY'
            else:
                st = 'RUNNING'
        elif st == 'BLOCKED': st = 'BLOCKED'"""
s = s.replace(old_st, new_st)

# Fix 3: Disable UNENDLICH
s = s.replace("if mode not in {'BEGRENZT', 'UNENDLICH'}:", "if mode not in {'BEGRENZT'}:")

with open("app/cannon/web.py", "w") as f:
    f.write(s)
