with open("scripts/agent_handoff_ledger.py", "r") as f:
    code = f.read()

code = code.replace(
    'logger.error',
    'print'
)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(code)
