from pathlib import Path

p = Path("scripts/agent_handoff_ledger.py")
content = p.read_text()

target_validate = """    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValidationError(f"record fields mismatch: missing={missing}, extra={extra}")"""

repl_validate = """    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        if all(m in ["TASK_SPECS", "TOMBSTONED_EDGES"] for m in missing) and not extra:
            pass # Backwards compatibility for new fields
        else:
            raise ValidationError(f"record fields mismatch: missing={missing}, extra={extra}")"""

if target_validate in content:
    content = content.replace(target_validate, repl_validate)
    print("Replaced validation check.")
else:
    print("WARNING: target_validate not found!")

target_default = """    reject_secrets(record)
    for field in RECORD_FIELDS:"""

repl_default = """    if "TASK_SPECS" not in record:
        record["TASK_SPECS"] = {}
    if "TOMBSTONED_EDGES" not in record:
        record["TOMBSTONED_EDGES"] = []
    reject_secrets(record)
    for field in RECORD_FIELDS:"""

if target_default in content:
    content = content.replace(target_default, repl_default)
    print("Replaced default initialization.")
else:
    print("WARNING: target_default not found!")

p.write_text(content)
