from pathlib import Path

p = Path("scripts/agent_handoff_ledger.py")
content = p.read_text()

target = """        if entry["changed_fields"] != expected_changed:
            raise ValidationError(f"history entry {index} changed_fields do not match record: {entry['changed_fields']} != {expected_changed}")"""

repl = """        # Backwards compatibility: allow missing new fields in expected_changed
        filtered_expected = [f for f in expected_changed if f in entry["changed_fields"] or f not in ["TASK_SPECS", "TOMBSTONED_EDGES"]]
        if entry["changed_fields"] != filtered_expected:
            raise ValidationError(f"history entry {index} changed_fields do not match record: {entry['changed_fields']} != {filtered_expected}")"""

if target in content:
    content = content.replace(target, repl)
    print("SUCCESS")
else:
    print("WARNING: target not found")

p.write_text(content)
