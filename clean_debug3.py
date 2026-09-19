with open("scripts/agent_handoff_ledger.py", "r") as f:
    code = f.read()

import re
code = re.sub(
    r'        print\(f"DEBUG RECOMPUTE CHANGED: \{changed\} bundle=\{bundle\[\'record\'\]\[\'CLEAN_IDLE\'\]\} new=\{record\[\'CLEAN_IDLE\'\]\}"\)\n',
    '',
    code
)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(code)
