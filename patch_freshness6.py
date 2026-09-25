import re
with open("tests/test_ledger_freshness_binding_epoch.py", "r") as f:
    content = f.read()

replacement = """    @patch("scripts.agent_handoff_ledger._verify_attestation")
    def test_evidence_at_47h_qualifies_as_fresh(self, mock_verify):
        mock_verify.return_value = {
            "verdict": "PASS",
            "producer_principal": "prod-ext",
            "verifier_principal": "ver-ext",
            "result_sha256": "fake-hash",
            "goal_id": "freshness-test",
            "binding": {"sha": SHA, "runtime": RUNTIME}
        }
        \"\"\"Evidence at 47 hours old is still within the 48h window.\"\"\"
        tmp = Path(tempfile.mkdtemp())
        path = tmp / "ledger.json"
    
        rec = _base_record()
        g = _base_guard()
        g["acceptance_predicate"]["required_results"] = ["ISSUE_STATE"]
        g["acceptance_predicate"]["results"] = {
            "ISSUE_STATE": {
                "status": "UNKNOWN",
                "observed_value": "PENDING",
                "evidence_urls": [],
            }
        }
        initialize(path, rec, g, 5.0)
    
        just_fresh = datetime.utcnow() - timedelta(hours=47)
        g1 = copy.deepcopy(g)
        g1["evidence"].append(_artifact("https://test.com/47h", _ts(just_fresh)))
        update(path, 0, {"TASKS_COMPLETED": 3}, "writer-a", 5.0, guard=g1)
        
        import scripts.agent_handoff_ledger as ahl
        bundle = ahl.load_bundle(path)
        introducer_map = {}
        first_observed_map = {}
        for h in bundle.get("history", []):
            h_updater = h.get("updated_by")
            for e in h.get("acceptance_guard", {}).get("evidence", []):
                url = e.get("source_url")
                if not url: continue
                if url not in introducer_map:
                    introducer_map[url] = set()
                introducer_map[url].add(h_updater)
                if url not in first_observed_map:
                    first_observed_map[url] = (h_updater, e.get("observed_at", h.get("timestamp")))
        evidence = bundle.get("acceptance_guard", {}).get("evidence", [])
        print("MOCK INTRODUCERS", introducer_map)
        for e in evidence:
            if e.get("source_url") == "https://test.com/47h":
                print("1:", e.get("source_type") == "MACHINE_ARTIFACT")
                print("2:", e.get("evidence_sha") == g["binding"]["current_sha"])
                print("3:", e.get("runtime_binding") == g["binding"]["runtime_identity"])
                print("4:", e.get("validity") == "VALID")
                print("5:", e.get("producer_id") not in introducer_map.get(e.get("source_url"), set()))
                print("6:", e.get("verifier_id") not in introducer_map.get(e.get("source_url"), set()))
                print("7:", "writer-b" not in introducer_map.get(e.get("source_url"), set()))
                t1 = datetime.strptime(first_observed_map.get(e.get("source_url"), (None, datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")))[1], "%Y-%m-%dT%H:%M:%SZ")
                t2 = datetime.strptime(e.get("observed_at"), "%Y-%m-%dT%H:%M:%SZ")
                diff = (t1 - t2).total_seconds()
                print("8:", diff, -ahl.MAX_FUTURE_CLOCK_SKEW_SECONDS <= diff <= ahl.MAX_EVIDENCE_AGE_SECONDS)
                
        result = update(path, 1, {"TASKS_COMPLETED": 4, "STATUS": "DONE"}, "writer-b", 5.0)
        assert result["acceptance_guard"]["transition_state"] == "CANONICAL_ACCEPTED\""""

content = re.sub(r'    @patch\(\"scripts\.agent_handoff_ledger\._verify_attestation\"\)\n    def test_evidence_at_47h_qualifies_as_fresh\(self, mock_verify\):.*?assert result\[\"acceptance_guard\"\]\[\"transition_state\"\] == \"CANONICAL_ACCEPTED\"', replacement, content, flags=re.DOTALL)

with open("tests/test_ledger_freshness_binding_epoch.py", "w") as f:
    f.write(content)
