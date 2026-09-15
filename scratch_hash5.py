import hashlib
import json

with open("coordination/mac_to_windows/archive/REQ-MAC-7B6D8CA4.json", "r") as f:
    req = json.load(f)

# try json.dumps
s1 = json.dumps(req, sort_keys=True, separators=(",", ":")).encode("utf-8")
print(hashlib.sha256(s1).hexdigest())

# try with different separators
s2 = json.dumps(req).encode("utf-8")
print(hashlib.sha256(s2).hexdigest())

