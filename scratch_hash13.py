import hashlib
import json

with open("coordination/windows_to_mac/results/REQ-MAC-7B6D8CA4.json", "r") as f:
    d = json.load(f)

target = "c7eecb7ae7ce30103bc5ef7a51b7d65af96a9615b74a43f4e232658d71759e42"

for k, v in d.items():
    if isinstance(v, str):
        if hashlib.sha256(v.encode('utf-8')).hexdigest() == target:
            print("MATCH:", k)
            exit(0)
print("No single field match.")
