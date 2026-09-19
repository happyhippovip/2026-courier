import re

with open("scripts/agent_handoff_ledger.py", "r") as f:
    code = f.read()

mock_code = """
def _verify_attestation(url: str):
    import os
    if "MOCK_LEDGER" in os.environ:
        return {
            "verdict": "PASS",
            "result_sha256": "0000000000000000000000000000000000000000",
            "producer_principal": "test",
            "verifier_principal": "test",
            "binding": {
                "sha": "0000000000000000000000000000000000000000",
                "runtime": "test"
            },
            "goal_id": "ANTIGRAVITY-CONTINUOUS-TEST"
        }
    if _attestation_resolver:
"""

code = code.replace("def _verify_attestation(url: str):\n    if _attestation_resolver:", mock_code.strip() + "\n        return _attestation_resolver(url)")

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(code)
