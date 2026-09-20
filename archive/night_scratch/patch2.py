import sys
content = open("scripts/agent_handoff_ledger.py").read()
content = content.replace(
    'if not changed and not guard_changed:\n            raise LedgerError("update makes no meaningful change")',
    'if not changed and not guard_changed:\n            print(f"DEBUG NO CHANGE: updates={updates} | record={bundle[\'record\']}")\n            raise LedgerError("update makes no meaningful change")'
)
open("scripts/agent_handoff_ledger.py", "w").write(content)
