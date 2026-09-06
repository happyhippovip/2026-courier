with open("scripts/courier_real_worker_adapters.py", "r") as f:
    lines = f.readlines()
for i in range(90, 100):
    print(repr(lines[i]))
