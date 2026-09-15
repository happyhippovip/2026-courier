import sys
path = "scripts/courier_safety_dispatcher.py"
data = open(path).read()
data = data.replace('print(f"DEBUG _mutate', '# print(f"DEBUG _mutate')
open(path, "w").write(data)
