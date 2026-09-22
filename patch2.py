with open("tests/test_DLQ01_trust_boundary.py", "r") as f:
    c = f.read()
c = c.replace('"runtime_identity": {"uid": "1", "user": "user"}',
              '"runtime_identity": {"uid": "1", "user": "user"},\n        "prompt_id": claimed.get("prompt_id")')
with open("tests/test_DLQ01_trust_boundary.py", "w") as f:
    f.write(c)

with open("tests/test_DLQ02_freshness_bound.py", "r") as f:
    c = f.read()
c = c.replace('"runtime_identity": {"uid": "1", "user": "user"}',
              '"runtime_identity": {"uid": "1", "user": "user"},\n        "prompt_id": claimed.get("prompt_id")')
with open("tests/test_DLQ02_freshness_bound.py", "w") as f:
    f.write(c)
