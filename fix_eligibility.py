import sys

with open("server/app.py", "r") as f:
    lines = f.readlines()

new_lines = []
skip = False

for line in lines:
    if line.strip() == 'if time.time() <= state.get("provider_locks", {}).get(lock_key, 0):':
        if "return False" in lines[lines.index(line)+1]:
            new_lines.append(line)
            new_lines.append('        if task.get("mode") != "NATIVE":\n')
            new_lines.append('            return False\n')
            skip = True
            continue
            
    if skip:
        if line.strip() == 'return False':
            skip = False
        continue

    new_lines.append(line)

with open("server/app.py", "w") as f:
    f.writelines(new_lines)

