with open("tests/test_DLQ01_trust_boundary.py", "r") as f:
    c = f.read()

# Add received_runtime_identity to verify calls
c = c.replace('"verdict": "PASS", "artifacts": result_json["artifacts"]',
              '"verdict": "PASS", "artifacts": result_json["artifacts"], "received_runtime_identity": result_json["runtime_identity"]')
with open("tests/test_DLQ01_trust_boundary.py", "w") as f:
    f.write(c)

with open("scripts/agent_handoff_ledger.py", "r") as f:
    ahl = f.read()
import re
match = re.search(r"RECORD_FIELDS = \{(.*?)\}", ahl, re.DOTALL)
fields = [m.strip().strip('"').strip("'") for m in match.group(1).split(",") if m.strip()]

# Generate a proper base_record
base_rec_str = "def base_record():\n    return {\n"
for f in fields:
    base_rec_str += f'        "{f}": "",\n'
base_rec_str += "    }"
print(base_rec_str)
