with open("tests/test_routing_acceptance_v1.py", "r") as f:
    code = f.read()

# Fix verify payloads
code = code.replace(
    '"received_runtime_identity": "mock-binding"',
    '"received_runtime_identity": "test", "verifier_id": "V1", "producer_id": "P1", "result_sha256": "0000"'
)

# Actually, the test was patched with my generic regex earlier, which added:
# `"received_runtime_identity": "mock-binding", "verifier_id": "V1", "producer_id": "P1", "result_sha256": "0000"`
# Wait, let's look at how test_routing_acceptance_v1 calls /tasks/verify.
