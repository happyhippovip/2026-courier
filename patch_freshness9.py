import re
with open("scripts/agent_handoff_ledger.py", "r") as f:
    content = f.read()

replacement = """        if updates.get("CLEAN_IDLE") == "YES" and (unproven or not has_physical_proof):

            raise CleanIdleError("CLEAN_IDLE=YES is forbidden without pre-existing physical proof and empty unproven edges")
        with open("/tmp/debug_has_proof.txt", "a") as df: df.write(f"HAS PHYSICAL PROOF: {has_physical_proof}\\n")
        if unproven or record.get("STATUS") in ("READY", "WAITING_PROVIDER", "DISPATCHED", "RUNNING"):"""

content = re.sub(r'        if updates.get\(\"CLEAN_IDLE\"\) == \"YES\" and \(unproven or not has_physical_proof\):\n\n            raise CleanIdleError\(\"CLEAN_IDLE=YES is forbidden without pre-existing physical proof and empty unproven edges\"\)\n\n        if unproven or record.get\(\"STATUS\"\) in \(\"READY\", \"WAITING_PROVIDER\", \"DISPATCHED\", \"RUNNING\"\):', replacement, content)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(content)
