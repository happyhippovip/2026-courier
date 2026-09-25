with open("tests/test_routing_acceptance_v1.py", "r") as f:
    c = f.read()

c = c.replace(
    'assert verified.status_code == 200',
    'assert verified.status_code == 200, verified.get_json()'
)

with open("tests/test_routing_acceptance_v1.py", "w") as f:
    f.write(c)

