with open("tests/test_antigravity_continuous.py", "r") as f:
    code = f.read()

code = code.replace(
    'env=dict(os.environ, MOCK_LEDGER=str(ledger_path), MOCK_BRANCH="test-branch", MOCK_SHA="0000000000000000000000000000000000000000", MOCK_TORTURE_TASK="1")',
    'env=dict(os.environ, MOCK_LEDGER=str(ledger_path), MOCK_BRANCH="test-branch", MOCK_SHA="0000000000000000000000000000000000000000", MOCK_TORTURE_TASK="1", MOCK_GOAL_ID="ANTIGRAVITY-CONTINUOUS-TEST")'
)

with open("tests/test_antigravity_continuous.py", "w") as f:
    f.write(code)
