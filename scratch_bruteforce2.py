import hashlib
import json
import itertools

with open("coordination/windows_to_mac/results/REQ-MAC-7B6D8CA4.json", "r") as f:
    d = json.load(f)

target = "c7eecb7ae7ce30103bc5ef7a51b7d65af96a9615b74a43f4e232658d71759e42"

def try_hash(obj):
    encoded = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if hashlib.sha256(encoded).hexdigest() == target:
        print("FOUND JSON MATCH!")
        print(list(obj.keys()))
        return True
    return False

keys = list(d.keys())
for r in range(1, len(keys)):
    for combo in itertools.combinations(keys, r):
        sub_obj = {k: d[k] for k in combo}
        if try_hash(sub_obj):
            exit(0)

print("No JSON subset match.")
