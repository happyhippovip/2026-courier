import re
with open("scripts/headless_night.py", "r") as f:
    c = f.read()

c = c.replace("'--disable-approval'", "'--dangerously-skip-permissions'")
with open("scripts/headless_night.py", "w") as f:
    f.write(c)

