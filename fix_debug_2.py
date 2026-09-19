import re

with open("scripts/agent_handoff_ledger.py", "r") as f:
    code = f.read()

debug_code = """
                        if not receipt:
                            print("DEBUG: receipt is None")
                        elif receipt.get("verdict") != "PASS":
                            print("DEBUG: verdict failed", receipt.get("verdict"))
                        elif receipt.get("result_sha256") != e.get("result_sha256"):
                            print("DEBUG: result_sha256 failed", type(receipt.get("result_sha256")), receipt.get("result_sha256"), type(e.get("result_sha256")), e.get("result_sha256"))
                        elif receipt.get("producer_principal") != e.get("producer_id"):
                            print("DEBUG: producer_principal failed", receipt.get("producer_principal"), e.get("producer_id"))
                        elif receipt.get("verifier_principal") != e.get("verifier_id"):
                            print("DEBUG: verifier_principal failed", receipt.get("verifier_principal"), e.get("verifier_id"))
                        elif receipt.get("binding", {}).get("sha") != e.get("evidence_sha"):
                            print("DEBUG: binding sha failed", receipt.get("binding", {}).get("sha"), e.get("evidence_sha"))
                        elif receipt.get("binding", {}).get("runtime") != e.get("runtime_binding"):
                            print("DEBUG: binding runtime failed", receipt.get("binding", {}).get("runtime"), e.get("runtime_binding"))
                        elif receipt.get("goal_id") != bundle.get("record", {}).get("GOAL"):
                            print("DEBUG: goal_id failed", receipt.get("goal_id"), bundle.get("record", {}).get("GOAL"))

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
