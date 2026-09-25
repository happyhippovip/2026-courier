import re

with open("tests/test_agent_handoff_ledger.py", "r") as f:
    content = f.read()

mock = """
    def test_acceptance_cannot_consume_same_update_evidence(self):
        def mock_attest(url):
            return {
                "verdict": "PASS",
                "producer_principal": "foreign-producer",
                "verifier_principal": "foreign-verifier",
                "result_sha256": None,
                "goal_id": "goal-1",
                "binding": {
                    "sha": "b" * 40,
                    "runtime": "b" * 40
                }
            }
        ledger_module._attestation_resolver = mock_attest
        try:
            with tempfile.TemporaryDirectory() as temporary:
"""

content = content.replace(
    "    def test_acceptance_cannot_consume_same_update_evidence(self):\n        with tempfile.TemporaryDirectory() as temporary:",
    mock
)

content = content.replace(
    """            self.assertEqual(
                followed["acceptance_guard"]["transition_state"],
                "CANONICAL_ACCEPTED",
            )""",
    """            self.assertEqual(
                followed["acceptance_guard"]["transition_state"],
                "CANONICAL_ACCEPTED",
            )
        finally:
            ledger_module._attestation_resolver = None"""
)

with open("tests/test_agent_handoff_ledger.py", "w") as f:
    f.write(content)
