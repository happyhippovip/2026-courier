import re

with open("scripts/agent_handoff_ledger.py", "r") as f:
    code = f.read()

code = code.replace(
    'receipt.get("binding", {}).get("runtime") == e.get("runtime_binding") and \\',
    'receipt.get("binding", {}).get("runtime") == e.get("runtime_binding") and \\\n            receipt.get("goal_id") == bundle["record"]["GOAL"] and \\'
)

new_check = """
        # Ensure any predicate PASS is backed by physically verified evidence
        for res_name, res_state in guard.get("acceptance_predicate", {}).get("results", {}).items():
            if res_state.get("status") == "PASS":
                for u in res_state.get("evidence_urls", []):
                    # Find the evidence block
                    e = next((item for item in guard.get("evidence", []) if item.get("source_url") == u), None)
                    if e and e.get("source_type") == "MACHINE_ARTIFACT":
                        receipt = _verify_attestation(u)
                        if not receipt or receipt.get("verdict") != "PASS" or \\
                           receipt.get("result_sha256") != e.get("result_sha256") or \\
                           receipt.get("producer_principal") != e.get("producer_id") or \\
                           receipt.get("verifier_principal") != e.get("verifier_id") or \\
                           receipt.get("binding", {}).get("sha") != e.get("evidence_sha") or \\
                           receipt.get("binding", {}).get("runtime") != e.get("runtime_binding") or \\
                           receipt.get("goal_id") != bundle.get("record", {}).get("GOAL"):
                            raise SelfCertificationError(f"predicate PASS relies on unverified or forged evidence {u}")
"""

code = code.replace(
    '        guard_changed = guard != bundle.get("acceptance_guard")',
    new_check.lstrip('\n') + '        guard_changed = guard != bundle.get("acceptance_guard")'
)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(code)
