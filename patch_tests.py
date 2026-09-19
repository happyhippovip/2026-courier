import os
files = [
    "tests/test_queue_independence.py",
    "tests/test_routing_acceptance_v1.py",
    "tests/test_restart_resume_torture.py"
]

for f in files:
    with open(f, "r") as file:
        code = file.read()
    
    code = code.replace(
        '"validity":"VALID","reason":"test"',
        '"validity":"VALID","reason":"test","producer_id":"producer_1","verifier_id":"verifier_1","result_sha256":"0000000000000000000000000000000000000000"'
    )
    with open(f, "w") as file:
        file.write(code)
