import hashlib
import json
import itertools

with open("coordination/windows_to_mac/results/REQ-MAC-7B6D8CA4.json", "r") as f:
    d = json.load(f)

target = "c7eecb7ae7ce30103bc5ef7a51b7d65af96a9615b74a43f4e232658d71759e42"
keys = ["schema_version", "mission_id", "windows_validation_request_id", "assignment_id", "status", "decision", "work_done", "evidence", "access_integrity", "files_changed", "side_effects_occurred", "blocker", "receipt_id", "receipt_hash", "two_level_done", "completed_at"]

def try_hash(s):
    if hashlib.sha256(s.encode('utf-8')).hexdigest() == target:
        print("FOUND STRING MATCH:", repr(s))
        return True
    return False

# Just iterating through all pairs, triples, etc. of values is too much, but let's try some standard concatenations
vals = []
for k in keys:
    if k in ["evidence", "content_integrity"]: continue
    v = d[k]
    if isinstance(v, list): v = json.dumps(v)
    elif isinstance(v, dict): v = json.dumps(v, sort_keys=True, separators=(',', ':'))
    elif isinstance(v, bool): v = str(v).lower()
    else: v = str(v)
    vals.append((k, v))

# Try values concatenated
import itertools
for r in range(1, 6):
    for combo in itertools.permutations(vals, r):
        s = "".join([x[1] for x in combo])
        if try_hash(s):
            print([x[0] for x in combo])
            exit(0)
            
# Also try JSON dumping specific subsets
print("No simple concatenation match.")
