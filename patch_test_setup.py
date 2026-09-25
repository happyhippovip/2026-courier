import re

with open("tests/test_agent_handoff_ledger.py", "r") as f:
    content = f.read()

setup_code = """    def setUp(self):
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

    def tearDown(self):
        ledger_module._attestation_resolver = None

"""

content = content.replace("class AgentHandoffLedgerTests(unittest.TestCase):\n", "class AgentHandoffLedgerTests(unittest.TestCase):\n" + setup_code)

with open("tests/test_agent_handoff_ledger.py", "w") as f:
    f.write(content)
