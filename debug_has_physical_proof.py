import re

with open("scripts/agent_handoff_ledger.py", "r") as f:
    code = f.read()

debug_code = """
        has_physical_proof = False
        for e in prior_evidence:
            if not (e.get("source_type") == "MACHINE_ARTIFACT"): continue
            if not (e.get("evidence_sha") == guard["binding"]["current_sha"]): continue
            if not (e.get("runtime_binding") == guard["binding"]["runtime_identity"]): continue
            if not (e.get("validity") == "VALID"): continue
            receipt = _verify_attestation(e.get("source_url", ""))
            if not receipt:
                logger.error(f"DEBUG: No receipt for {e.get('source_url')}")
                continue
            if not (receipt.get("verdict") == "PASS"): continue
            if not (receipt.get("result_sha256") == e.get("result_sha256")): continue
            if not (receipt.get("producer_principal") == e.get("producer_id")): continue
            if not (receipt.get("verifier_principal") == e.get("verifier_id")): continue
            if not (receipt.get("binding", {}).get("sha") == e.get("evidence_sha")): continue
            if not (receipt.get("binding", {}).get("runtime") == e.get("runtime_binding")): continue
            if not (receipt.get("goal_id") == bundle["record"]["GOAL"]): continue
            if not (e.get("producer_id") not in introducer_map.get(e.get("source_url"), set())): continue
            if not (e.get("verifier_id") not in introducer_map.get(e.get("source_url"), set())): continue
            if not (updated_by not in introducer_map.get(e.get("source_url"), set())): continue
            
            t1 = datetime.strptime(first_observed_map.get(e.get("source_url"), (None, datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")))[1], "%Y-%m-%dT%H:%M:%SZ")
            t2 = datetime.strptime(e["observed_at"], "%Y-%m-%dT%H:%M:%SZ")
            diff = (t1 - t2).total_seconds()
            if not (-MAX_FUTURE_CLOCK_SKEW_SECONDS <= diff <= MAX_EVIDENCE_AGE_SECONDS):
                logger.error(f"DEBUG: Age check failed! diff={diff}")
                continue
            
            has_physical_proof = True
            break
"""

code = re.sub(r'has_physical_proof = any\([\s\S]*?for e in prior_evidence\n\s*\)', debug_code.strip(), code)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(code)
