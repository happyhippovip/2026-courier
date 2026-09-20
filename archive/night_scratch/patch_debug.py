import sys
content = open("scripts/courier_continue.py").read()
content = content.replace(
    'new_bundle = update(\n        ledger_path,',
    'print(f"DEBUG UPDATES: {updates}")\n    new_bundle = update(\n        ledger_path,'
)
open("scripts/courier_continue.py", "w").write(content)
