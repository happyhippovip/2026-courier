import re

with open("scripts/agent_handoff_ledger.py", "r") as f:
    code = f.read()

code = re.sub(
    r'"producer_id",\s*"verifier_id"\s*\}\)',
    '"producer_id",\n                "verifier_id",\n                "result_sha256"\n            })',
    code
)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(code)
