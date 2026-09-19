import re

with open("app/cannon/web.py", "r") as f:
    s = f.read()

old_st = """        elif is_active:
            if not helper_active:
                st = 'READY'
            else:
                st = 'RUNNING'"""
new_st = """        elif is_active:
            if not helper_active:
                if CHILD is not None and CHILD.poll() not in (0, None):
                    st = 'ERROR'
                else:
                    st = 'READY'
            else:
                st = 'RUNNING'"""

s = s.replace(old_st, new_st)

with open("app/cannon/web.py", "w") as f:
    f.write(s)
