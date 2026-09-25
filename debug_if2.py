import re
with open("scripts/agent_handoff_ledger.py", "r") as f:
    content = f.read()

replacement = """        has_physical_proof = False
        for e in prior_evidence:
            with open("/tmp/debug_receipt2.txt", "a") as df:
                df.write(f"EVIDENCE: {e.get('source_url')} type: {e.get('source_type')}\\n")
                if e.get("source_type") == "MACHINE_ARTIFACT":
                    df.write(f"sha: {e.get('evidence_sha')} == {guard['binding']['current_sha']}\\n")
                    df.write(f"runtime: {e.get('runtime_binding')} == {guard['binding']['runtime_identity']}\\n")
                    df.write(f"validity: {e.get('validity')}\\n")
                    df.write(f"prod: {e.get('producer_id')} not in {introducer_map.get(e.get('source_url'), set())}\\n")
                    df.write(f"ver: {e.get('verifier_id')} not in {introducer_map.get(e.get('source_url'), set())}\\n")
                    df.write(f"upd: {updated_by} not in {introducer_map.get(e.get('source_url'), set())}\\n")
                    t1 = datetime.strptime(first_observed_map.get(e.get("source_url"), (None, datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")))[1], "%Y-%m-%dT%H:%M:%SZ")
                    t2 = datetime.strptime(e.get("observed_at"), "%Y-%m-%dT%H:%M:%SZ")
                    diff = (t1 - t2).total_seconds()
                    df.write(f"skew: {-MAX_FUTURE_CLOCK_SKEW_SECONDS} <= {diff} <= {MAX_EVIDENCE_AGE_SECONDS}\\n")
                    receipt = _verify_attestation(e.get("source_url"))
                    df.write(f"receipt: {receipt}\\n")
                    if receipt:
                        df.write(f"receipt check:\\n")
                        df.write(f"verdict: {receipt.get('verdict')}\\n")
                        df.write(f"prod: {receipt.get('producer_principal')} == {e.get('producer_id')}\\n")
                        df.write(f"ver: {receipt.get('verifier_principal')} == {e.get('verifier_id')}\\n")
                        df.write(f"sha256: {receipt.get('result_sha256')} == {e.get('result_sha256')}\\n")
                        df.write(f"goal: {receipt.get('goal_id')} == {bundle.get('record', {}).get('GOAL')}\\n")
                        b = receipt.get("binding", {})
                        df.write(f"b sha: {b.get('sha')} == {guard['binding']['current_sha']}\\n")
                        df.write(f"b run: {b.get('runtime')} == {guard['binding']['runtime_identity']}\\n")
            if ("""

content = re.sub(r'        has_physical_proof = False\n        for e in prior_evidence:\n            if \(', replacement, content)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(content)
