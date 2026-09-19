import re

with open("tests/conftest.py", "r") as f:
    code = f.read()

code = code.replace(
    "monkeypatch.setattr(agent_handoff_ledger, '_attestation_resolver', lambda url: MatchDict())",
    "print('PATCHING RESOLVER!')\n        monkeypatch.setattr(agent_handoff_ledger, '_attestation_resolver', lambda url: MatchDict())"
)

with open("tests/conftest.py", "w") as f:
    f.write(code)
