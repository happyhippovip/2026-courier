import os
with open("server/app.py", "r") as f:
    c = f.read()

c = c.replace('is_crash_loop = durable_result.get("raw_result", {}).get("reason") == "CRASH_LOOP"', 'is_crash_loop = data.get("raw_result", {}).get("reason") == "CRASH_LOOP"')

with open("server/app.py", "w") as f:
    f.write(c)

