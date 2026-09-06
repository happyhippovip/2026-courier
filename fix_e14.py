with open("tests/test_write_reliability.py", "r") as f:
    content = f.read()

content = content.replace(
    '"capability_required": "implementation",\n            "preferred_agent": "CLI1"',
    '"capability_required": "local repo analysis",\n            "preferred_agent": "CLI1"'
)

with open("tests/test_write_reliability.py", "w") as f:
    f.write(content)
