import os
with open("scripts/mac_worker/daemon.py", "r") as f:
    c = f.read()

c = c.replace('"""\n                "status"', '\n                "status"')

with open("scripts/mac_worker/daemon.py", "w") as f:
    f.write(c)

