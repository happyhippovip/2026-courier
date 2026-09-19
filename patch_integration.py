import re
with open("tests/test_server_integration_contract.py", "r") as f:
    code = f.read()

# Let's fix ALL verify payloads in this file to use the claimed server_binding
code = code.replace(
    '"received_runtime_identity": "test"',
    '"received_runtime_identity": claimed["server_binding"], "verifier_id": "V1", "producer_id": "P1", "result_sha256": "0000"'
)

with open("tests/test_server_integration_contract.py", "w") as f:
    f.write(code)
