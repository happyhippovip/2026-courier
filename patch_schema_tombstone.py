import json
from pathlib import Path

p = Path("schemas/agent_handoff_ledger.schema.json")
schema = json.load(p.open())

if "TOMBSTONED_EDGES" not in schema["$defs"]["record"]["properties"]:
    schema["$defs"]["record"]["properties"]["TOMBSTONED_EDGES"] = {
        "$ref": "#/$defs/stringList"
    }
    schema["$defs"]["record"]["required"].append("TOMBSTONED_EDGES")

with p.open("w") as f:
    json.dump(schema, f, indent=2)

print("SUCCESS")
