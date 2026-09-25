with open("tests/test_tomato_two_torture.py", "r") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "http://127.0.0.1:8080/" in line and "add-generic-password" in line:
        if "start_server" in "".join(lines[:i][-20:]): # roughly in the setup block
            lines[i] = line.replace("8080/", "8081")

with open("tests/test_tomato_two_torture.py", "w") as f:
    f.writelines(lines)
