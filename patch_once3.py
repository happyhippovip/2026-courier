import re

with open("scripts/courier_continue.py", "r") as f:
    content = f.read()

# I will just write a custom script to patch the args.once logic
old_block1 = """        if args.once and not running_tasks:
                sys.exit(0)"""
new_block1 = """        if args.once and not running_tasks and 'once_dispatched' in locals():
                sys.exit(0)"""
content = content.replace(old_block1, new_block1)

old_block2 = """        if args.once and not running_tasks:
            sys.exit(0)"""
new_block2 = """        if args.once and not running_tasks and 'once_dispatched' in locals():
            sys.exit(0)"""
content = content.replace(old_block2, new_block2)

# Set once_dispatched when we submit tasks
content = content.replace(
    """        if newly_submitted or running_tasks:
            print(f"\\nCurrently running {len(running_tasks)} tasks concurrently.")""",
    """        if newly_submitted:
            once_dispatched = True
        if newly_submitted or running_tasks:
            print(f"\\nCurrently running {len(running_tasks)} tasks concurrently.")"""
)

with open("scripts/courier_continue.py", "w") as f:
    f.write(content)
print("Patched once3")
