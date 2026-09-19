import re

with open("scripts/agent_handoff_ledger.py", "r") as f:
    code = f.read()

code = code.replace(
    '"producer_id",\n                "verifier_id"',
    '"producer_id",\n                "verifier_id",\n                "result_sha256"'
)
with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(code)
