import hashlib
import json
import itertools

with open("coordination/mac_to_windows/archive/REQ-MAC-7B6D8CA4.json", "r") as f:
    req = json.load(f)

target = "c7eecb7ae7ce30103bc5ef7a51b7d65af96a9615b74a43f4e232658d71759e42"

def try_hash(obj):
    encoded = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if hashlib.sha256(encoded).hexdigest() == target:
        print("FOUND JSON MATCH!", obj.keys())
        exit(0)

keys = list(req.keys())
for r in range(1, len(keys)+1):
    for combo in itertools.combinations(keys, r):
        sub = {k: req[k] for k in combo}
        try_hash(sub)

print("No match.")
