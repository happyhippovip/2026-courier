import re
with open("tests/test_routing_acceptance_v1.py", "r") as f:
    content = f.read()

target = """        json={
            "task_id": "first",
            "result_id": res_payload["result_id"],
            "verifier_id": "independent-verifier",
            "verdict": "PASS",
            "artifacts": [],
        },"""

replacement = """        json={
            "task_id": "first",
            "result_id": res_payload["result_id"],
            "verifier_id": "independent-verifier",
            "verdict": "PASS",
            "artifacts": [],
            "runtime_identity": SERVER_BINDING,
        },"""

content = content.replace(target, replacement)

with open("tests/test_routing_acceptance_v1.py", "w") as f:
    f.write(content)
