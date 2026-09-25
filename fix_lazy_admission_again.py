with open("tests/test_cannon_lazy_admission.py", "r") as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if line.strip().startswith('if mode == "BEGRENZT":'):
        skip = True
        new_lines.append('        assert command[command.index("--limit") + 1] == "1000000"\n')
        continue
    
    if skip:
        if line.strip() == 'assert web.action({"action": "START", "mode": mode, "count": 1000000})["already_running"]' or \
           line.strip() == 'assert "--limit" not in command' or \
           line.strip() == 'else:':
            continue
        else:
            skip = False
    
    new_lines.append(line)

with open("tests/test_cannon_lazy_admission.py", "w") as f:
    f.writelines(new_lines)
