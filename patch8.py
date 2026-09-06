with open("scripts/courier_founder_mode.py", "r") as f:
    content = f.read()

content = content.replace('if status == "BLOCKED":', 'if status in ["BLOCKED", "FAILED"]:')

with open("scripts/courier_founder_mode.py", "w") as f:
    f.write(content)
