import re

with open("scripts/agent_handoff_ledger.py", "r") as f:
    code = f.read()

code = code.replace(
    'if "MOCK_LEDGER" in os.environ:',
    'if "MOCK_LEDGER" in os.environ:\n        print("MOCK HIT!")'
)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(code)
