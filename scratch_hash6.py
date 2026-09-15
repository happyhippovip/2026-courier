import hashlib
import json

with open("coordination/mac_to_windows/archive/REQ-MAC-7B6D8CA4.json", "r") as f:
    d = json.load(f)

s = json.dumps(d, sort_keys=True, separators=(',', ':')).encode('utf-8')
print(hashlib.sha256(s).hexdigest())

