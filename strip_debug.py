with open("scripts/agent_handoff_ledger.py", "r") as f:
    lines = f.readlines()

out = []
for line in lines:
    if line.strip().startswith("print(\"DEBUG"):
        continue
    out.append(line)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write("".join(out))
