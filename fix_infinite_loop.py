import re

with open("scripts/courier_continue.py", "r") as f:
    code = f.read()

code = code.replace(
    "if args.once and not running_tasks and ('done_edges' not in locals() or not done_edges) and 'once_dispatched' in locals():",
    "if args.once and not running_tasks and 'once_dispatched' in locals():"
)

with open("scripts/courier_continue.py", "w") as f:
    f.write(code)
