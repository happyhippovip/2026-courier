import re

with open("scripts/agent_handoff_ledger.py", "r") as f:
    code = f.read()

debug_code = """
                        if not receipt:
                            raise Exception("DEBUG: receipt is None")
                        elif receipt.get("verdict") != "PASS":
                            raise Exception("DEBUG: verdict failed " + str(receipt.get("verdict")))
                        elif receipt.get("result_sha256") != e.get("result_sha256"):
                            raise Exception("DEBUG: result_sha256 failed " + str(type(receipt.get("result_sha256"))) + " " + str(receipt.get("result_sha256")) + " " + str(type(e.get("result_sha256"))) + " " + str(e.get("result_sha256")))
                        elif receipt.get("producer_principal") != e.get("producer_id"):
                            raise Exception("DEBUG: producer_principal failed " + str(receipt.get("producer_principal")) + " " + str(e.get("producer_id")))
                        elif receipt.get("verifier_principal") != e.get("verifier_id"):
                            raise Exception("DEBUG: verifier_principal failed " + str(receipt.get("verifier_principal")) + " " + str(e.get("verifier_id")))
                        elif receipt.get("binding", {}).get("sha") != e.get("evidence_sha"):
                            raise Exception("DEBUG: binding sha failed " + str(receipt.get("binding", {}).get("sha")) + " " + str(e.get("evidence_sha")))
                        elif receipt.get("binding", {}).get("runtime") != e.get("runtime_binding"):
                            raise Exception("DEBUG: binding runtime failed " + str(receipt.get("binding", {}).get("runtime")) + " " + str(e.get("runtime_binding")))
                        elif receipt.get("goal_id") != bundle.get("record", {}).get("GOAL"):
                            raise Exception("DEBUG: goal_id failed " + str(receipt.get("goal_id")) + " " + str(bundle.get("record", {}).get("GOAL")))

                        if not receipt or receipt.get("verdict") != "PASS" or \\
                               receipt.get("result_sha256") != e.get("result_sha256") or \\
                               receipt.get("producer_principal") != e.get("producer_id") or \\
                               receipt.get("verifier_principal") != e.get("verifier_id") or \\
                               receipt.get("binding", {}).get("sha") != e.get("evidence_sha") or \\
                               receipt.get("binding", {}).get("runtime") != e.get("runtime_binding") or \\
                               receipt.get("goal_id") != bundle.get("record", {}).get("GOAL"):
                                raise SelfCertificationError(f"predicate PASS relies on unverified or forged evidence {u}")
"""

code = re.sub(r'if not receipt:\n.*raise SelfCertificationError.*?\n', debug_code.strip() + '\n', code, flags=re.DOTALL)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(code)
