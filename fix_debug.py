import re

with open("scripts/agent_handoff_ledger.py", "r") as f:
    code = f.read()

debug_code = """
                            if not receipt or receipt.get("verdict") != "PASS" or \\
                               receipt.get("result_sha256") != e.get("result_sha256") or \\
                               receipt.get("producer_principal") != e.get("producer_id") or \\
                               receipt.get("verifier_principal") != e.get("verifier_id") or \\
                               receipt.get("binding", {}).get("sha") != e.get("evidence_sha") or \\
                               receipt.get("binding", {}).get("runtime") != e.get("runtime_binding") or \\
                               receipt.get("goal_id") != bundle.get("record", {}).get("GOAL"):
                                raise SelfCertificationError(f"predicate PASS relies on unverified or forged evidence {u}")
"""

code = re.sub(r'if not receipt or receipt\.get\("verdict"\) != "PASS".*?raise SelfCertificationError.*?\n', debug_code.strip() + '\n', code, flags=re.DOTALL)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(code)
