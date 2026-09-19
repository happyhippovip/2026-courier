with open("scripts/agent_handoff_ledger.py", "r") as f:
    code = f.read()

code = code.replace(
    '            receipt.get("goal_id") == bundle["record"]["GOAL"] and \\\n            receipt.get("goal_id") == bundle["record"]["GOAL"] and \\',
    '            receipt.get("goal_id") == bundle["record"]["GOAL"] and \\'
)

# Remove the duplicate predicate PASS block
# Let's just use regex to remove one of them
import re
code = re.sub(
    r'(# Ensure any predicate PASS is backed by physically verified evidence.*?raise SelfCertificationError\(f"predicate PASS relies on unverified or forged evidence \{u\}"\)\s+){2}',
    r'\1',
    code,
    flags=re.DOTALL
)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(code)
