import re
with open("scripts/agent_handoff_ledger.py", "r") as f:
    content = f.read()

content = content.replace("prior_evidence = [e for e in evidence if e in old_evidence]", "prior_evidence = [e for e in evidence if e in old_evidence]\n        with open('/tmp/debug_ledger.txt', 'a') as df:\n            df.write(f'PRIOR EVIDENCE LEN {len(prior_evidence)}\\n')")

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(content)
