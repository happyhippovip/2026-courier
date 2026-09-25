with open("tests/test_routing_acceptance_v1.py", "r") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if '"runtime_identity": SERVER_BINDING,' in line and "artifacts" in lines[i-1]:
        lines[i] = line.replace("runtime_identity", "received_runtime_identity")

with open("tests/test_routing_acceptance_v1.py", "w") as f:
    f.writelines(lines)
