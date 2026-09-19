import os, re

for filename in ["tests/test_DLQ02_freshness_bound.py", "tests/test_ledger_duplicate_semantics_contract.py"]:
    with open(filename, "r") as f:
        code = f.read()
    code = code.replace("import agent_handoff_ledger as ahl", "from scripts import agent_handoff_ledger as ahl")
    with open(filename, "w") as f:
        f.write(code)

with open("tests/test_agent_handoff_ledger.py", "r") as f:
    code = f.read()
code = code.replace("import agent_handoff_ledger", "from scripts import agent_handoff_ledger")
with open("tests/test_agent_handoff_ledger.py", "w") as f:
    f.write(code)
