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
        \"\"\"Evidence at 47 hours old is still within the 48h window.\"\"\""""

content = re.sub(r'    def test_evidence_at_47h_qualifies_as_fresh\(self\):\n        \"\"\"Evidence at 47 hours old is still within the 48h window\.\"\"\"', replacement, content)

with open("tests/test_ledger_freshness_binding_epoch.py", "w") as f:
    f.write(content)
