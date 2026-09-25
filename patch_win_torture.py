with open("tests/test_windows_runtime_torture.py", "r") as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if 'server_env["PYTHONPATH"] = os.path.abspath(".")' in line:
        lines.insert(i+1, '            server_env["PORT"] = "8082"\n')
        break
with open("tests/test_windows_runtime_torture.py", "w") as f:
    f.writelines(lines)
