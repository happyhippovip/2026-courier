import re
files = [
    "tests/test_queue_independence.py",
    "tests/test_routing_acceptance_v1.py",
    "tests/test_restart_resume_torture.py"
]

for f in files:
    with open(f, "r") as file:
        code = file.read()
    
    # We need to find the `env["MOCK_LEDGER"]` line and insert `env["MOCK_GOAL_ID"] = "..."`
    # Let's extract the GOAL from the code.
    match = re.search(r'"GOAL":\s*"([^"]+)"', code)
    if match:
        goal = match.group(1)
        code = code.replace(
            'env["MOCK_LEDGER"] =',
            f'env["MOCK_GOAL_ID"] = "{goal}"\n    env["MOCK_LEDGER"] ='
        )
    with open(f, "w") as file:
        file.write(code)
