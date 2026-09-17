with open("scripts/courier_continue.py", "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "if args.once and not running_tasks and 'once_dispatched' in locals():" in line:
        new_lines.append(line.replace("if args.once and not running_tasks and 'once_dispatched' in locals():", "if args.once and not running_tasks:"))
    else:
        new_lines.append(line)

with open("scripts/courier_continue.py", "w") as f:
    f.writelines(new_lines)
