import re
with open("scripts/agent_handoff_ledger.py", "r") as f:
    content = f.read()

replacement = """        for e in prior_evidence:
            if (
                e.get("source_type") == "MACHINE_ARTIFACT"
            ):
                with open("/tmp/debug_ledger2.txt", "a") as df:
                    df.write(f"checking {e.get('source_url')}\\n")
                    t1 = datetime.strptime(first_observed_map.get(e.get("source_url"), (None, datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")))[1], "%Y-%m-%dT%H:%M:%SZ")
                    t2 = datetime.strptime(e.get("observed_at", datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")), "%Y-%m-%dT%H:%M:%SZ")
                    diff = (t1 - t2).total_seconds()
                    df.write(f"t1={t1}, t2={t2}, diff={diff}\\n")
                    df.write(f"skew={-MAX_FUTURE_CLOCK_SKEW_SECONDS <= diff <= MAX_EVIDENCE_AGE_SECONDS}\\n")
            if ("""

content = re.sub(r'        for e in prior_evidence:\n            if \(', replacement, content)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(content)
