with open("scripts/agent_handoff_ledger.py", "r") as f:
    code = f.read()

code = code.replace(
    '                           receipt.get("result_sha256") != e.get("result_sha256"):\n                            \n        # Enforce stale proof rules:',
    '                           receipt.get("result_sha256") != e.get("result_sha256"):\n                            raise SelfCertificationError(f"predicate PASS requires verified receipt for {url}")\n        # Enforce stale proof rules:'
)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(code)
