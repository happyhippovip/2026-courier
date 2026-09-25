import re
with open("tests/test_routing_acceptance_v1.py", "r") as f:
    content = f.read()

content = content.replace('"received_runtime_identity": SERVER_BINDING,', '"runtime_identity": SERVER_BINDING,')

replacement = """        verified = motor.post(
            "/tasks/verify",
            headers=verifier_auth(),
            json={
                "task_id": "first",
                "result_id": res_payload["result_id"],
                "verifier_id": "independent-verifier",
                "verdict": "PASS",
                "artifacts": [],
                "received_runtime_identity": SERVER_BINDING,
            },
        )"""

content = re.sub(r'        verified = motor.post\(\n            \"/tasks/verify\",\n            headers=verifier_auth\(\),\n            json=\{\n                \"task_id\": \"first\",\n                \"result_id\": res_payload\[\"result_id\"\],\n                \"verifier_id\": \"independent-verifier\",\n                \"verdict\": \"PASS\",\n                \"artifacts\": \[\],\n                \"runtime_identity\": SERVER_BINDING,\n            \},\n        \)', replacement, content)

with open("tests/test_routing_acceptance_v1.py", "w") as f:
    f.write(content)
