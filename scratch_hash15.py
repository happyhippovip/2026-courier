import hashlib
import json

target = "c7eecb7ae7ce30103bc5ef7a51b7d65af96a9615b74a43f4e232658d71759e42"
def test(s):
    if hashlib.sha256(s.encode('utf-8')).hexdigest() == target:
        print("MATCH:", s)
        exit(0)

# What if it's hashing just the file name?
test("REQ-MAC-7B6D8CA4.json")
test("REQ-MAC-7B6D8CA4")
test("WINDOWS_COMPATIBILITY")
test("PASS")
test("MAC_AUTONOMOUS_OPERATIONS")

# What if the canonical input is the dictionary without some keys?
with open("coordination/windows_to_mac/results/REQ-MAC-7B6D8CA4.json", "r") as f:
    d = json.load(f)

# Try computing SHA256 of the json representation without content_integrity and evidence
from copy import deepcopy
for exclude in [['content_integrity', 'evidence'], ['content_integrity'], ['evidence', 'content_integrity', 'receipt_id', 'completed_at']]:
    d_copy = deepcopy(d)
    for k in exclude:
        d_copy.pop(k, None)
    
    s1 = json.dumps(d_copy, sort_keys=True, separators=(',', ':')).encode('utf-8')
    test(s1.decode('utf-8'))
    
    s2 = json.dumps(d_copy).encode('utf-8')
    test(s2.decode('utf-8'))

print("No match.")
