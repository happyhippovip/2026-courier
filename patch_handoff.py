with open("scripts/agent_handoff_ledger.py", "r") as f:
    code = f.read()

old_mock = '''
        return {
            "verdict": "PASS",
            "result_sha256": "0000000000000000000000000000000000000000",
            "producer_principal": "test",
            "verifier_principal": "test",
            "binding": {
                "sha": "0000000000000000000000000000000000000000",
                "runtime": os.environ.get("MOCK_RUNTIME_IDENTITY", "0000000000000000000000000000000000000000")
            },
            "goal_id": os.environ.get("MOCK_GOAL_ID", "TEST-GOAL")
        }'''

new_mock = '''
        return {
            "verdict": "PASS",
            "result_sha256": "0000000000000000000000000000000000000000",
            "producer_principal": "producer_1",
            "verifier_principal": "verifier_1",
            "binding": {
                "sha": "0000000000000000000000000000000000000000",
                "runtime": os.environ.get("MOCK_RUNTIME_IDENTITY", "0000000000000000000000000000000000000000")
            },
            "goal_id": os.environ.get("MOCK_GOAL_ID", "TEST-GOAL")
        }'''

code = code.replace(old_mock, new_mock)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(code)
