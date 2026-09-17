import re

with open("scripts/courier_continue.py", "r") as f:
    content = f.read()

# Replace the first args.once block
old_block = """            if args.once:
                sys.exit(0)"""

new_block = """            if args.once and not running_tasks:
                sys.exit(0)"""

content = content.replace(old_block, new_block)

with open("scripts/courier_continue.py", "w") as f:
    f.write(content)
print("Patched once2")
