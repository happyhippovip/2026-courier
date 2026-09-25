import re

with open("scripts/agent_handoff_ledger.py", "r") as f:
    content = f.read()

# 1. Add has_unverified_pass_evidence = False
content = content.replace("defer_to_clean_idle_gate = updates.get(\"CLEAN_IDLE\") == \"YES\" and (unproven or not has_physical_proof)", 
    "has_unverified_pass_evidence = False\n        defer_to_clean_idle_gate = updates.get(\"CLEAN_IDLE\") == \"YES\" and (unproven or not has_physical_proof)")

# 2. Change the if not pe: raise block
old_pe_block = """                        pe = next((ev for ev in prior_evidence if ev.get("source_url") == url), None)
                        if not pe:
                            raise SelfCertificationError(f"predicate PASS requires prior evidence for {url}")"""

new_pe_block = """                        pe = next((ev for ev in prior_evidence if ev.get("source_url") == url), None)
                        if not pe:
                            has_unverified_pass_evidence = True
                            continue"""
content = content.replace(old_pe_block, new_pe_block)

# 3. Change elif not unproven and has_physical_proof:
content = content.replace("elif not unproven and has_physical_proof:",
    "elif not unproven and has_physical_proof and not has_unverified_pass_evidence:")

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(content)
