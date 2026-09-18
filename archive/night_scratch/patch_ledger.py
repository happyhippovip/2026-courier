import sys
content = open("scripts/agent_handoff_ledger.py").read()
content = content.replace(
    'if not changed and guard == bundle.get("acceptance_guard"):\n            raise LedgerError("update makes no meaningful change")',
    'if not changed and guard == bundle.get("acceptance_guard"):\n            print(f"DEBUG NO CHANGE: updates={updates} | record={bundle[\'record\']}")\n            raise LedgerError("update makes no meaningful change")'
)
open("scripts/agent_handoff_ledger.py", "w").write(content)
