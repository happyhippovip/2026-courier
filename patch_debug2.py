with open("scripts/agent_handoff_ledger.py", "r") as f:
    code = f.read()

code = code.replace(
    'print(f"DEBUG: receipt={type(receipt)} dict={dict(receipt) if receipt else None}"); if not receipt or receipt.get("verdict") != "PASS" or \\',
    'print(f"DEBUG: receipt={type(receipt)} dict={dict(receipt) if receipt else None}")\n                        if not receipt or receipt.get("verdict") != "PASS" or \\'
)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(code)
