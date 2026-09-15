import hashlib
import json

with open("coordination/windows_to_mac/results/REQ-MAC-7B6D8CA4.json", "r") as f:
    d = json.load(f)

print(d["evidence"])
print(d["content_integrity"])
