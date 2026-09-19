with open("scripts/agent_handoff_ledger.py", "r") as f:
    code = f.read()

import re
code = re.sub(
    r'                        print\(f"DEBUG: receipt=\{type\(receipt\)\} dict=\{dict\(receipt\) if receipt else None\}"\)\n',
    '',
    code
)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(code)
