import re
with open("scripts/agent_handoff_ledger.py", "r") as f:
    content = f.read()

replacement = """        for e in prior_evidence:
            print("CHECKING EVIDENCE", e)
            print("1", e.get("source_type") == "MACHINE_ARTIFACT")
            print("2", e.get("evidence_sha") == guard["binding"]["current_sha"])
            print("3", e.get("runtime_binding") == guard["binding"]["runtime_identity"])
            print("4", e.get("validity") == "VALID")
            print("5", e.get("producer_id") not in introducer_map.get(e.get("source_url"), set()))
            print("6", e.get("verifier_id") not in introducer_map.get(e.get("source_url"), set()))
            print("7", updated_by not in introducer_map.get(e.get("source_url"), set()))
            t1 = datetime.strptime(first_observed_map.get(e.get("source_url"), (None, datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")))[1], "%Y-%m-%dT%H:%M:%SZ")
            t2 = datetime.strptime(e["observed_at"], "%Y-%m-%dT%H:%M:%SZ")
            diff = (t1 - t2).total_seconds()
            print("8", -MAX_FUTURE_CLOCK_SKEW_SECONDS <= diff <= MAX_EVIDENCE_AGE_SECONDS, diff)
            if ("""

content = re.sub(r'        for e in prior_evidence:\n            if \(', replacement, content)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(content)
