import hashlib
import json
import itertools

with open("coordination/windows_to_mac/results/REQ-MAC-7B6D8CA4.json", "r") as f:
    d = json.load(f)

target = "c7eecb7ae7ce30103bc5ef7a51b7d65af96a9615b74a43f4e232658d71759e42"

def check(s):
    if hashlib.sha256(s.encode("utf-8")).hexdigest() == target:
        print("MATCH:", repr(s))
        return True
    return False

check(d["evidence"])
check(d["evidence"].split("SHA256:")[1] if "SHA256:" in d["evidence"] else "")
check(d["windows_validation_request_id"] + d["status"] + d["evidence"])
check(d["windows_validation_request_id"] + d["status"] + d["work_done"])

# what if the evidence contains the hash of something else?
# EXECUTION_EXIT_0_SHA256:c7eecb7ae7ce30103bc5ef7a51b7d65af96a9615b74a43f4e232658d71759e42
# Maybe the hash is of the command output, and since we don't have it, we can't compute it?
