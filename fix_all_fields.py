import json
from pathlib import Path
import re

# 1. Update Schema
p_schema = Path("schemas/agent_handoff_ledger.schema.json")
schema = json.load(p_schema.open())

if "TASK_SPECS" not in schema["$defs"]["record"]["properties"]:
    schema["$defs"]["record"]["properties"]["TASK_SPECS"] = {
        "type": "object",
        "additionalProperties": {
            "type": "object",
            "properties": {
                "instruction": {"type": "string", "minLength": 1},
                "target_agent": {"type": "string"},
                "capabilities": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["instruction"]
        }
    }
    schema["$defs"]["record"]["required"].append("TASK_SPECS")

with p_schema.open("w") as f:
    json.dump(schema, f, indent=2)

# 2. Update Python Script
p_script = Path("scripts/agent_handoff_ledger.py")
content = p_script.read_text()

if '"TASK_SPECS",' not in content:
    content = content.replace('"TOMBSTONED_EDGES",', '"TOMBSTONED_EDGES",\n    "TASK_SPECS",\n    "RUNNING_TASKS",')

if "DICT_FIELDS = {" not in content:
    content = content.replace('LIST_FIELDS = {', 'DICT_FIELDS = {\n    "TASK_SPECS",\n    "RUNNING_TASKS",\n}\nLIST_FIELDS = {')

# 3. Add dict validation
val_target = """        if field in LIST_FIELDS:
            if not isinstance(value, list) or any(
                not isinstance(item, str) or not item.strip() for item in value
            ):
                raise ValidationError(f"{field} must be an array of non-empty strings")"""
val_repl = """        if field in DICT_FIELDS:
            if not isinstance(value, dict):
                raise ValidationError(f"{field} must be a dictionary")
        elif field in LIST_FIELDS:
            if not isinstance(value, list) or any(
                not isinstance(item, str) or not item.strip() for item in value
            ):
                raise ValidationError(f"{field} must be an array of non-empty strings")"""
if val_target in content:
    content = content.replace(val_target, val_repl)

# 4. Backward compat
compat_target = 'all(m in ["TASK_SPECS", "TOMBSTONED_EDGES", "RUNNING_TASKS"] for m in missing)'
# Already added? Let's check.
if 'all(m in ["TASK_SPECS", "TOMBSTONED_EDGES"] for m in missing)' in content:
    content = content.replace('all(m in ["TASK_SPECS", "TOMBSTONED_EDGES"] for m in missing)', 'all(m in ["TASK_SPECS", "TOMBSTONED_EDGES", "RUNNING_TASKS"] for m in missing)')

if 'f not in ["TASK_SPECS", "TOMBSTONED_EDGES"]' in content:
    content = content.replace('f not in ["TASK_SPECS", "TOMBSTONED_EDGES"]', 'f not in ["TASK_SPECS", "TOMBSTONED_EDGES", "RUNNING_TASKS"]')

p_script.write_text(content)
print("SUCCESS")
