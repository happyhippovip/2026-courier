import re
with open("tests/test_headless_night_offline.py", "r") as f:
    c = f.read()

c = c.replace("'--disable-approval'", "'--dangerously-skip-permissions'")
c = c.replace('"--disable-approval"', '"--dangerously-skip-permissions"')
with open("tests/test_headless_night_offline.py", "w") as f:
    f.write(c)

