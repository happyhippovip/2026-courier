class MockReceipt(dict):
    def get(self, key, default=None):
        if key == "verdict": return "PASS"
        if key == "producer_principal": return "producer_1"
        if key == "verifier_principal": return "verifier_1"
        if key == "result_sha256": return "0" * 40
        if key == "goal_id": return "test-goal"
        if key == "binding": return self
        if key == "sha": return "0" * 40
        if key == "runtime": return __import__("os").environ.get("MOCK_RUNTIME_IDENTITY", "0" * 40)
        return default

receipt = MockReceipt()
print("verdict:", receipt.get("verdict"))
print("producer_principal:", receipt.get("producer_principal") == "producer_1")
print("verifier_principal:", receipt.get("verifier_principal") == "verifier_1")
print("result_sha256:", receipt.get("result_sha256") == "0" * 40)
print("goal_id:", receipt.get("goal_id") == "test-goal")
print("sha:", receipt.get("binding", {}).get("sha") == "0" * 40)
print("runtime:", receipt.get("binding", {}).get("runtime") == "0" * 40)

import json
# Wait, let's see what is checked exactly in test_courier_continue.py!
print(len("0" * 40))

