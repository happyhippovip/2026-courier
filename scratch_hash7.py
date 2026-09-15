import hashlib
import json
import itertools

with open("coordination/windows_to_mac/results/REQ-MAC-7B6D8CA4.json", "r") as f:
    d = json.load(f)

target = "c7eecb7ae7ce30103bc5ef7a51b7d65af96a9615b74a43f4e232658d71759e42"

def check(s):
    if hashlib.sha256(s.encode("utf-8")).hexdigest() == target:
        print("MATCH:", repr(s))
        exit(0)

# The legacy schema is request_id + status + observed_behavior
# So it's 3 fields. Let's try permutations of all string fields up to length 4.
vals = []
for k, v in d.items():
    if isinstance(v, str) and "SHA256" not in v:
        vals.append(v)

for r in range(1, 5):
    for combo in itertools.permutations(vals, r):
        s = "".join(combo)
        check(s)
        # Also try with spaces or other separators?
        # In legacy there is NO separator: f"{req_id}{status}{observed_behavior}"

# what about boolean fields?
vals_with_bool = vals.copy()
vals_with_bool.append("true")
vals_with_bool.append("false")
vals_with_bool.append("True")
vals_with_bool.append("False")

for r in range(1, 5):
    for combo in itertools.permutations(vals_with_bool, r):
        s = "".join(combo)
        check(s)

print("No match found")
