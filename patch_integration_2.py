with open("tests/test_server_integration_contract.py", "r") as f:
    code = f.read()

# Fix verify payloads in this file to use task["server_binding"]
code = code.replace(
    'claimed["server_binding"], "verifier_id": "V1", "producer_id": "P1", "result_sha256": "0000"',
    'task["server_binding"], "producer_id": "P1", "result_sha256": "0000"'
)

with open("tests/test_server_integration_contract.py", "w") as f:
    f.write(code)
