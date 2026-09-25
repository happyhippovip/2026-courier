from pathlib import Path
p = Path("scripts/agent_handoff_ledger.py")
content = p.read_text()

# Remove TASK_SPECS from LIST_FIELDS
list_fields_target = """LIST_FIELDS = {
    "PROVEN_EDGES",
    "UNPROVEN_EDGES",
    "TASK_SPECS",
    "ACTIVE_WRITERS",
    "COLLISION_SCOPE",
    "LAST_EVIDENCE",
}"""

list_fields_replacement = """DICT_FIELDS = {
    "TASK_SPECS",
}
LIST_FIELDS = {
    "PROVEN_EDGES",
    "UNPROVEN_EDGES",
    "ACTIVE_WRITERS",
    "COLLISION_SCOPE",
    "LAST_EVIDENCE",
}"""

if list_fields_target in content:
    content = content.replace(list_fields_target, list_fields_replacement)
else:
    print("WARNING: list_fields_target not found!")


# Add DICT_FIELDS validation
validation_target = """        if field in LIST_FIELDS:
            if not isinstance(value, list) or any(
                not isinstance(item, str) or not item.strip() for item in value
            ):
                raise ValidationError(f"{field} must be an array of non-empty strings")"""

validation_replacement = """        if field in DICT_FIELDS:
            if not isinstance(value, dict):
                raise ValidationError(f"{field} must be a dict")
        elif field in LIST_FIELDS:
            if not isinstance(value, list) or any(
                not isinstance(item, str) or not item.strip() for item in value
            ):
                raise ValidationError(f"{field} must be an array of non-empty strings")"""

if validation_target in content:
    content = content.replace(validation_target, validation_replacement)
else:
    print("WARNING: validation_target not found!")

p.write_text(content)
print("SUCCESS")
