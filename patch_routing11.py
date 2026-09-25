import re
with open("tests/test_routing_acceptance_v1.py", "r") as f:
    content = f.read()

content = content.replace('"runtime_identity": SERVER_BINDING,', '"received_runtime_identity": SERVER_BINDING,')

with open("tests/test_routing_acceptance_v1.py", "w") as f:
    f.write(content)
