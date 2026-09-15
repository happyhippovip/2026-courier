import hashlib
import json

with open("coordination/windows_to_mac/results/REQ-MAC-7B6D8CA4.json", "r") as f:
    d = json.load(f)

target = "c7eecb7ae7ce30103bc5ef7a51b7d65af96a9615b74a43f4e232658d71759e42"

def test(s):
    if hashlib.sha256(s.encode('utf-8')).hexdigest() == target:
        print("MATCH:", s)
        exit(0)

# legacy is request_id + status + observed_behavior
# maybe windows is windows_validation_request_id + status + work_done?
s = d["windows_validation_request_id"] + d["status"] + d["work_done"]
test(s)
print("No match.")
