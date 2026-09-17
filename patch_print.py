with open("scripts/courier_continue.py", "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "def update_ledger(" in line:
        new_lines.append(line)
        new_lines.append("    print(f'DEBUG update_ledger called with expected revision: {bundle[\"revision\"]}')\n")
    elif "def check_freshness(" in line:
        new_lines.append(line)
        new_lines.append("    print(f'DEBUG check_freshness called')\n")
    elif "return bundle" in line and "def check_freshness" not in line: # Be careful not to replace wrong returns
        pass
    else:
        new_lines.append(line)

with open("scripts/courier_continue.py", "w") as f:
    f.writelines(new_lines)
