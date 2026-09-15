import sys
path = "scripts/courier_safety_dispatcher.py"
data = open(path).read()
lines = data.split("\n")
for i, line in enumerate(lines):
    if 'self.last_result_status = "FAIL"' in line:
        lines[i] = line.replace('self.last_result_status = "FAIL"', f'print("FAIL SET ON LINE {i+1}"); self.last_result_status = "FAIL"')
open(path, "w").write("\n".join(lines))
