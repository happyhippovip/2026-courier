with open("scripts/agent_handoff_ledger.py", "r") as f:
    code = f.read()

code = code.replace(
    'receipt.get("binding", {}).get("runtime") == e.get("runtime_binding") and \\',
    'receipt.get("binding", {}).get("runtime") == e.get("runtime_binding") and \\\n            receipt.get("goal_id") == bundle["record"]["GOAL"] and \\'
)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(code)
