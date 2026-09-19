with open("tests/test_restart_resume_torture.py", "r") as file:
    code = file.read()

code = code.replace(
    'env["MOCK_LEDGER"] = str(ledger_path)',
    'env["MOCK_GOAL_ID"] = "QUEUE-INDEPENDENT-TEST"\n    env["MOCK_LEDGER"] = str(ledger_path)'
)

with open("tests/test_restart_resume_torture.py", "w") as file:
    file.write(code)
