with open("tests/test_agent_handoff_ledger.py", "r") as f:
    code = f.read()

import re

# Remove the mock.patch with context
code = re.sub(
    r'            with mock\.patch\("scripts\.agent_handoff_ledger\._verify_attestation"\) as mock_verify:\n                mock_verify\.return_value = \{\n.*?\n                \}\n',
    """            ledger_module._attestation_resolver = lambda url: {
                "verdict": "PASS",
                "producer_principal": "foreign-producer",
                "verifier_principal": "foreign-verifier",
                "result_sha256": "0000000000000000000000000000000000000000",
                "goal_id": "test",
                "binding": {
                    "sha": "b" * 40,
                    "runtime": "b" * 40
                }
            }
""",
    code,
    flags=re.DOTALL
)

with open("tests/test_agent_handoff_ledger.py", "w") as f:
    f.write(code)
