import hashlib
import json
import itertools

with open("coordination/windows_to_mac/results/REQ-MAC-7B6D8CA4.json", "r") as f:
    d = json.load(f)

target = "c7eecb7ae7ce30103bc5ef7a51b7d65af96a9615b74a43f4e232658d71759e42"

vals = []
for k in ["windows_validation_request_id", "status", "decision", "work_done", "access_integrity", "receipt_id", "receipt_hash"]:
    vals.append(d[k])

for r in range(1, len(vals)+1):
    for combo in itertools.permutations(vals, r):
        s = "".join(combo)
        if hashlib.sha256(s.encode('utf-8')).hexdigest() == target:
            print("MATCH FOUND:", combo)
            exit(0)

print("No string concat match.")
