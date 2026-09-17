with open("scripts/courier_continue.py", "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "while True:" in line:
        new_lines.append(line)
        new_lines.append("        print('DEBUG: Top of while loop')\n")
    elif "bundle = check_freshness(ledger_path, branch, sha)" in line:
        new_lines.append(line)
        new_lines.append("        print('DEBUG: After check_freshness')\n")
    elif "tasks = compute_frontier(record)" in line:
        new_lines.append(line)
        new_lines.append("        print('DEBUG: After compute_frontier')\n")
    elif "if not safe_executable_tasks:" in line:
        new_lines.append("        print('DEBUG: Checking safe_executable_tasks')\n")
        new_lines.append(line)
    elif "for edge_name, future in list(running_tasks.items()):" in line:
        new_lines.append("        print('DEBUG: Checking done futures')\n")
        new_lines.append(line)
    elif "for t in safe_executable_tasks:" in line and "newly_submitted = []" not in line and "if t[\"edge_name\"] not in running_tasks:" not in line:
        new_lines.append("        print('DEBUG: Submitting new tasks')\n")
        new_lines.append(line)
    elif "import time" in line:
        new_lines.append("        print('DEBUG: Sleeping...')\n")
        new_lines.append(line)
    elif "if args.once and not running_tasks:" in line:
        new_lines.append("        print('DEBUG: Checking args.once')\n")
        new_lines.append(line)
    else:
        new_lines.append(line)

with open("scripts/courier_continue.py", "w") as f:
    f.writelines(new_lines)
