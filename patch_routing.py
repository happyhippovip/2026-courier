import re
with open("tests/test_routing_acceptance_v1.py", "r") as f:
    content = f.read()

replacement = """        "result_id": result_id,
        "status": status,
        "runtime_identity": "TEST-RUNTIME","""

content = content.replace("""        "result_id": result_id,
        "status": status,""", replacement)

with open("tests/test_routing_acceptance_v1.py", "w") as f:
    f.write(content)
