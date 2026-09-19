with open("scripts/agent_handoff_ledger.py", "r") as f:
    code = f.read()

import re
code = re.sub(
    r'        class MockReceipt\(dict\):.*?(?=        return MockReceipt\(\))        return MockReceipt\(\)',
    '''        return {
            "verdict": "PASS",
            "producer_principal": "producer_1",
            "verifier_principal": "verifier_1",
            "result_sha256": "0" * 40,
            "goal_id": "test-goal",
            "binding": {
                "sha": "0" * 40,
                "runtime": __import__("os").environ.get("MOCK_RUNTIME_IDENTITY", "0" * 40)
            },
            "sha": "0" * 40,
            "runtime": __import__("os").environ.get("MOCK_RUNTIME_IDENTITY", "0" * 40)
        }''',
    code, flags=re.DOTALL
)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(code)
