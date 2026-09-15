import hashlib
import json

with open("coordination/windows_to_mac/results/REQ-MAC-7B6D8CA4.json", "r") as f:
    d = json.load(f)

req_id = d.get("windows_validation_request_id")
status = d.get("status")
evidence = d.get("evidence")
work_done = d.get("work_done")
decision = d.get("decision")
files_changed = d.get("files_changed")

def check(s):
    if hashlib.sha256(s.encode("utf-8")).hexdigest() == "c7eecb7ae7ce30103bc5ef7a51b7d65af96a9615b74a43f4e232658d71759e42":
        print("MATCH:", s)

check(f"{req_id}{status}{decision}")
check(f"{req_id}{status}{files_changed}")
check(f"{req_id}{status}{evidence}")
