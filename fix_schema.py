import json

with open("schemas/agent_handoff_ledger.schema.json", "r") as f:
    schema = json.load(f)

# Add TASK_SPECS to the record definition
schema["$defs"]["record"]["properties"]["TASK_SPECS"] = {
    "type": "object",
    "additionalProperties": {
        "type": "object",
        "properties": {
            "instruction": {
                "type": "string",
                "minLength": 1
            },
            "target_agent": {
                "type": "string"
            },
            "capabilities": {
                "type": "array",
                "items": {
                    "type": "string"
                }
            }
        },
        "required": ["instruction"]
    }
}

# Optional: Add it to required if we want, but it's probably better as optional for backwards compatibility,
# or we can add it to required and initialize it to {} in the init script.
# Let's add it to required so it matches the other fields.
schema["$defs"]["record"]["required"].append("TASK_SPECS")

with open("schemas/agent_handoff_ledger.schema.json", "w") as f:
    json.dump(schema, f, indent=2)

print("SUCCESS")
