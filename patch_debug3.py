with open("scripts/agent_handoff_ledger.py", "r") as f:
    code = f.read()

import re
code = re.sub(
    r'        changed = sorted\(field for field in RECORD_FIELDS if bundle\["record"\]\[field\] != record\[field\]\)',
    '        changed = sorted(field for field in RECORD_FIELDS if bundle["record"][field] != record[field])\n        print(f"DEBUG RECOMPUTE CHANGED: {changed} bundle={bundle[\'record\'][\'CLEAN_IDLE\']} new={record[\'CLEAN_IDLE\']}")',
    code
)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(code)
