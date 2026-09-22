import re
with open("tests/test_DLQ01_trust_boundary.py", "r") as f:
    c = f.read()
    
c = c.replace('"artifacts": [{"path": "a.txt", "sha256": hashlib.sha256(b"a\\n").hexdigest()}]',
              '"artifacts": [{"path": "a.txt", "sha256": hashlib.sha256(b"a\\n").hexdigest()}],\n        "runtime_identity": {"uid": "1", "user": "user"}')
with open("tests/test_DLQ01_trust_boundary.py", "w") as f:
    f.write(c)

with open("tests/test_DLQ02_freshness_bound.py", "r") as f:
    c = f.read()
c = c.replace('"artifacts": [{"path": "a.txt", "sha256": hashlib.sha256(b"a\\n").hexdigest()}]',
              '"artifacts": [{"path": "a.txt", "sha256": hashlib.sha256(b"a\\n").hexdigest()}],\n        "runtime_identity": {"uid": "1", "user": "user"}')
with open("tests/test_DLQ02_freshness_bound.py", "w") as f:
    f.write(c)
