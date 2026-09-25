import re
with open("tests/test_agent_handoff_ledger.py", "r") as f:
    content = f.read()

content = content.replace('"observed_at": "2026-09-17T18:00:00Z",', '"observed_at": ledger_module.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),')

with open("tests/test_agent_handoff_ledger.py", "w") as f:
    f.write(content)

