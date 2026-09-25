import re
from pathlib import Path

p = Path("scripts/agent_handoff_ledger.py")
content = p.read_text()

# Add TASK_SPECS to REQUIRED_FIELDS
if '"UNPROVEN_EDGES",' in content and '"TASK_SPECS",' not in content:
    content = content.replace('"UNPROVEN_EDGES",', '"UNPROVEN_EDGES",\n    "TASK_SPECS",')

# Add DICT_FIELDS below LIST_FIELDS
if 'DICT_FIELDS = {' not in content and 'LIST_FIELDS = {' in content:
    content = content.replace('LIST_FIELDS = {', 'DICT_FIELDS = {\n    "TASK_SPECS",\n}\nLIST_FIELDS = {')

# Find validate_record
validate_target = """    for field in LIST_FIELDS:
        val = record.get(field, [])
        if not isinstance(val, list):
            raise ValidationError(f"{field} must be a list")"""

validate_replacement = """    for field in LIST_FIELDS:
        val = record.get(field, [])
        if not isinstance(val, list):
            raise ValidationError(f"{field} must be a list")

    for field in DICT_FIELDS:
        val = record.get(field, {})
        if not isinstance(val, dict):
            raise ValidationError(f"{field} must be a dict")"""

if validate_target in content:
    content = content.replace(validate_target, validate_replacement)
else:
    print("validate_target not found!")

p.write_text(content)
print("SUCCESS")
