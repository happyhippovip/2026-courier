with open("scripts/courier_continue.py", "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "return bundle" in line:
        new_lines.append("    print(f'DEBUG check_freshness returning bundle with revision: {bundle[\"revision\"]}')\n")
        new_lines.append(line)
    else:
        new_lines.append(line)

with open("scripts/courier_continue.py", "w") as f:
    f.writelines(new_lines)
