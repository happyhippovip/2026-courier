import json
from pathlib import Path

p = Path("schemas/agent_handoff_ledger.schema.json")
schema = json.load(p.open())

if "RUNNING_TASKS" not in schema["$defs"]["record"]["properties"]:
    schema["$defs"]["record"]["properties"]["RUNNING_TASKS"] = {
        "type": "object",
        "additionalProperties": {
            "type": "string",
            "minLength": 1
        }
    }
    schema["$defs"]["record"]["required"].append("RUNNING_TASKS")

with p.open("w") as f:
    json.dump(schema, f, indent=2)

print("SUCCESS")
