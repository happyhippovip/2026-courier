import re
with open("scripts/agent_handoff_ledger.py", "r") as f:
    code = f.read()

new_code = """
        unproven = record.get("UNPROVEN_EDGES", [])
        
        # Enforce that any predicate PASS is backed by a valid receipt
        for name, result in guard.get("acceptance_predicate", {}).get("results", {}).items():
            if result.get("status") == "PASS":
                for url in result.get("evidence_urls", []):
                    # Find matching evidence in prior_evidence
                    e = next((ev for ev in prior_evidence if ev.get("source_url") == url), None)
                    if not e or e.get("validity") != "VALID" or e.get("source_type") != "MACHINE_ARTIFACT":
                        raise SelfCertificationError(f"predicate PASS requires valid MACHINE_ARTIFACT evidence for {url}")
                    receipt = _verify_attestation(url)
                    if not receipt or receipt.get("verdict") != "PASS" or \\
                       receipt.get("producer_principal") != e.get("producer_id") or \\
                       receipt.get("verifier_principal") != e.get("verifier_id") or \\
                       receipt.get("result_sha256") != e.get("result_sha256"):
                        raise SelfCertificationError(f"predicate PASS requires verified receipt for {url}")
"""

code = code.replace("        unproven = record.get(\"UNPROVEN_EDGES\", [])", new_code.strip("\n"))

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(code)
