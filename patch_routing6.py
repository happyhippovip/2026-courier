import re
with open("tests/test_routing_acceptance_v1.py", "r") as f:
    content = f.read()

replacement = """
    result_id = "result-first-success"
    res_payload = result_for(first, "W", result_id, "SUCCESS")
    received = motor.post(
        "/tasks/result",
        headers=auth(),
        json=res_payload,
    )
    assert received.status_code == 200

    verified = motor.post(
        "/tasks/verify",
        headers=verifier_auth(),
        json={
            "task_id": "first",
            "result_id": res_payload["result_id"],
            "verifier_id": "independent-verifier",
            "verdict": "PASS",
            "artifacts": [],
        },
    )
    assert verified.status_code == 200"""

content = re.sub(r'\n    result_id = \"result-first-success\".*?assert verified\.status_code == 200', replacement, content, flags=re.DOTALL)

with open("tests/test_routing_acceptance_v1.py", "w") as f:
    f.write(content)
