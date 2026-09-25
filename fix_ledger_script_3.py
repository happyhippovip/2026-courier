from pathlib import Path
p = Path("scripts/agent_handoff_ledger.py")
content = p.read_text()

validation_target = """    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValidationError(f"record fields mismatch: missing={missing}, extra={extra}")"""

validation_replacement = """    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    
    # Backwards compatibility: TASK_SPECS is optional for older records
    if missing == ["TASK_SPECS"] and not extra:
        pass
    elif actual != expected:
        raise ValidationError(f"record fields mismatch: missing={missing}, extra={extra}")"""

if validation_target in content:
    content = content.replace(validation_target, validation_replacement)
else:
    print("WARNING: validation_target not found!")

# We also need to default it if it's missing so the rest of the code works
default_target = """    reject_secrets(record)
    for field in RECORD_FIELDS:"""

default_replacement = """    if "TASK_SPECS" not in record:
        record["TASK_SPECS"] = {}
        
    reject_secrets(record)
    for field in RECORD_FIELDS:"""

if default_target in content:
    content = content.replace(default_target, default_replacement)
else:
    print("WARNING: default_target not found!")

p.write_text(content)
print("SUCCESS")
