import sys
with open("tests/test_server_integration_contract.py", "r") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if line.strip() == 'failed["artifacts"] = []':
        # Get the indentation of this line
        indent = line[:len(line) - len(line.lstrip())]
        lines.insert(i+1, indent + 'ident = {k: v for k, v in failed.items() if k != "result_id"}\n')
        lines.insert(i+2, indent + 'failed["result_id"] = "result-" + _canonical_hash(ident)\n')
        break

with open("tests/test_server_integration_contract.py", "w") as f:
    f.writelines(lines)
