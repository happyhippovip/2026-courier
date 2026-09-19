import re

with open("scripts/agent_handoff_ledger.py", "r") as f:
    code = f.read()

code = code.replace(
    'if not changed and not guard_changed:',
    'guard_changed = guard != bundle.get("acceptance_guard")\n        if not changed and not guard_changed:'
)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(code)
