import re
with open("scripts/agent_handoff_ledger.py", "r") as f:
    code = f.read()

new_has_physical_proof = """
        has_physical_proof = False
        for e in prior_evidence:
            if (
                e.get("source_type") == "MACHINE_ARTIFACT" and
                e.get("evidence_sha") == guard["binding"]["current_sha"] and
                e.get("runtime_binding") == guard["binding"]["runtime_identity"] and
                e.get("validity") == "VALID" and
                e.get("producer_id") not in introducer_map.get(e.get("source_url"), set()) and
                e.get("verifier_id") not in introducer_map.get(e.get("source_url"), set()) and
                updated_by not in introducer_map.get(e.get("source_url"), set()) and
                (-MAX_FUTURE_CLOCK_SKEW_SECONDS <=
                 (datetime.strptime(first_observed_map.get(e.get("source_url"), (None, datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")))[1], "%Y-%m-%dT%H:%M:%SZ") - datetime.strptime(e["observed_at"], "%Y-%m-%dT%H:%M:%SZ")).total_seconds() <=
                 MAX_EVIDENCE_AGE_SECONDS)
            ):
                receipt = _verify_attestation(e.get("source_url"))
                print(f"DEBUG e['producer_id']: {e.get('producer_id')}")
                print(f"DEBUG receipt prod: {receipt.get('producer_principal')}")
                print(f"DEBUG verdict: {receipt.get('verdict')}")
                print(f"DEBUG equal prod? {receipt.get('producer_principal') == e.get('producer_id')}")
                if receipt and receipt.get("verdict") == "PASS":
                    if receipt.get("producer_principal") == e.get("producer_id") and \\
                       receipt.get("verifier_principal") == e.get("verifier_id") and \\
                       receipt.get("result_sha256") == e.get("result_sha256") and \\
                       receipt.get("goal_id") == bundle.get("record", {}).get("GOAL"):
                        b = receipt.get("binding", {})
                        if b.get("sha") == guard["binding"]["current_sha"] and \\
                           b.get("runtime") == guard["binding"]["runtime_identity"]:
                            has_physical_proof = True
                            print("DEBUG set has_physical_proof = True")
                            break
        print(f"DEBUG has_physical_proof evaluated to: {has_physical_proof}")
"""

code = re.sub(
    r'        has_physical_proof = False\n.*?break\n',
    new_has_physical_proof.lstrip("\n"),
    code,
    flags=re.DOTALL
)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(code)
