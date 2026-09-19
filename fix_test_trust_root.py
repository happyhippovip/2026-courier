import re

with open("tests/test_ledger_attestation_trust_root.py", "r") as f:
    code = f.read()

code = code.replace(
    'agent_handoff_ledger._attestation_resolver = lambda url, expected_sha: True',
    'agent_handoff_ledger._attestation_resolver = lambda url: {"verdict": "PASS"}'
)

with open("tests/test_ledger_attestation_trust_root.py", "w") as f:
    f.write(code)
