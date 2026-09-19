import re

with open("scripts/courier_continue.py", "r") as f:
    code = f.read()

code = re.sub(r'if edge in \["PUBLIC DEPLOYMENT.*?time\.sleep\(20\)', '', code, flags=re.DOTALL)

with open("scripts/courier_continue.py", "w") as f:
    f.write(code)
