with open("scripts/agent_handoff_ledger.py", "r") as f:
    lines = f.readlines()

new_lines = []
in_has_physical_proof = False
for line in lines:
    if "first_observed_map[url] = e.get(\"observed_at\")" in line:
        new_lines.append(line.replace("e.get(\"observed_at\")", "(e.get(\"observed_at\"), h.get(\"timestamp_utc\"))"))
    elif "has_physical_proof = any(" in line:
        in_has_physical_proof = True
        new_lines.append("""
        has_physical_proof = False
        for e in prior_evidence:
            url = e.get("source_url")
            first_obs_tuple = first_observed_map.get(url, (e.get("observed_at"), datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")))
            time_diff = (datetime.strptime(first_obs_tuple[1], "%Y-%m-%dT%H:%M:%SZ") - datetime.strptime(e["observed_at"], "%Y-%m-%dT%H:%M:%SZ")).total_seconds()
            print(f"DEBUG: url={url} diff={time_diff}")
            if e.get("source_url") == "https://github.com/example/project/actions/runs/stale-1":
                print("C1:", e.get("source_type") == "MACHINE_ARTIFACT")
                print("C2:", e.get("evidence_sha") == guard["binding"]["current_sha"], e.get("evidence_sha"), guard["binding"]["current_sha"])
                print("C3:", e.get("runtime_binding") == guard["binding"]["runtime_identity"], e.get("runtime_binding"), guard["binding"]["runtime_identity"])
                print("C4:", e.get("validity") == "VALID")
                print("C5:", e.get("producer_id") not in introducer_map.get(url, set()), introducer_map.get(url, set()))
                print("C6:", e.get("verifier_id") not in introducer_map.get(url, set()))
                print("C7:", updated_by not in introducer_map.get(url, set()), updated_by)
                print("C8:", -MAX_FUTURE_CLOCK_SKEW_SECONDS <= time_diff <= MAX_EVIDENCE_AGE_SECONDS)
            if (e.get("source_type") == "MACHINE_ARTIFACT" and
                e.get("evidence_sha") == guard["binding"]["current_sha"] and
                e.get("runtime_binding") == guard["binding"]["runtime_identity"] and
                e.get("validity") == "VALID" and
                e.get("producer_id") not in introducer_map.get(url, set()) and
                e.get("verifier_id") not in introducer_map.get(url, set()) and
                updated_by not in introducer_map.get(url, set()) and
                -MAX_FUTURE_CLOCK_SKEW_SECONDS <= time_diff <= MAX_EVIDENCE_AGE_SECONDS):
                has_physical_proof = True
                break
""")
    elif in_has_physical_proof:
        if "for e in prior_evidence" in line:
            pass
        elif ")" in line and line.strip() == ")":
            in_has_physical_proof = False
        continue
    elif "first_obs = first_observed_map.get(url, e.get(\"observed_at\"))" in line:
        new_lines.append(line.replace("e.get(\"observed_at\")", "(e.get(\"observed_at\"), None)[0]").replace("first_observed_map.get(url", "first_observed_map.get(url, (e.get(\"observed_at\"), None))[0] #"))
    else:
        new_lines.append(line)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.writelines(new_lines)
