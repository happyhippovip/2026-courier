import re
with open("scripts/agent_handoff_ledger.py", "r") as f:
    content = f.read()

replacement = """        for e in prior_evidence:
            try:
                t1 = datetime.strptime(first_observed_map.get(e.get("source_url"), (None, datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")))[1], "%Y-%m-%dT%H:%M:%SZ")
                t2 = datetime.strptime(e.get("observed_at", datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")), "%Y-%m-%dT%H:%M:%SZ")
                diff = (t1 - t2).total_seconds()
                cond = (
                    e.get("source_type") == "MACHINE_ARTIFACT" and
                    e.get("evidence_sha") == guard["binding"]["current_sha"] and
                    e.get("runtime_binding") == guard["binding"]["runtime_identity"] and
                    e.get("validity") == "VALID" and
                    e.get("producer_id") not in introducer_map.get(e.get("source_url"), set()) and
                    e.get("verifier_id") not in introducer_map.get(e.get("source_url"), set()) and
                    updated_by not in introducer_map.get(e.get("source_url"), set()) and
                    (-MAX_FUTURE_CLOCK_SKEW_SECONDS <= diff <= MAX_EVIDENCE_AGE_SECONDS)
                )
                with open("/tmp/debug_ledger.txt", "a") as df:
                    df.write(f"EVIDENCE: {e.get('source_url')} -> {cond}\\n")
                    df.write(f"  type: {e.get('source_type')}\\n")
                    df.write(f"  sha: {e.get('evidence_sha')}\\n")
                    df.write(f"  runtime: {e.get('runtime_binding')}\\n")
                    df.write(f"  validity: {e.get('validity')}\\n")
                    df.write(f"  prod not in intro: {e.get('producer_id') not in introducer_map.get(e.get('source_url'), set())}\\n")
                    df.write(f"  ver not in intro: {e.get('verifier_id') not in introducer_map.get(e.get('source_url'), set())}\\n")
                    df.write(f"  upd not in intro: {updated_by not in introducer_map.get(e.get('source_url'), set())}\\n")
                    df.write(f"  time skew: {-MAX_FUTURE_CLOCK_SKEW_SECONDS <= diff <= MAX_EVIDENCE_AGE_SECONDS} ({diff})\\n")
            except Exception as ex:
                with open("/tmp/debug_ledger.txt", "a") as df:
                    df.write(f"EXC: {ex}\\n")
            if ("""

content = re.sub(r'        for e in prior_evidence:\n            if \(', replacement, content)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(content)
