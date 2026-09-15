import hashlib
import json
import itertools

with open("coordination/windows_to_mac/results/REQ-MAC-7B6D8CA4.json", "r") as f:
    d = json.load(f)

target = "c7eecb7ae7ce30103bc5ef7a51b7d65af96a9615b74a43f4e232658d71759e42"
keys = sorted(d.keys())

for r in range(1, len(keys)+1):
    for combo in itertools.combinations(keys, r):
        # build dict
        sub = {k: d[k] for k in combo}
        # dumps without space
        s1 = json.dumps(sub, sort_keys=True, separators=(',', ':')).encode('utf-8')
        if hashlib.sha256(s1).hexdigest() == target:
            print("MATCH JSON COMPACT:", combo)
            exit(0)
        # dumps with space
        s2 = json.dumps(sub, sort_keys=True).encode('utf-8')
        if hashlib.sha256(s2).hexdigest() == target:
            print("MATCH JSON NORMAL:", combo)
            exit(0)
        
        # also try concatenation of values
        s_val = "".join(str(d[k]) for k in combo)
        if hashlib.sha256(s_val.encode('utf-8')).hexdigest() == target:
            print("MATCH CONCAT:", combo)
            exit(0)
        
        # also try concatenation of key+value
        s_kv = "".join(f"{k}{d[k]}" for k in combo)
        if hashlib.sha256(s_kv.encode('utf-8')).hexdigest() == target:
            print("MATCH KV CONCAT:", combo)
            exit(0)

print("No match found.")
