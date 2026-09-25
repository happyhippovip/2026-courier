from pathlib import Path

p = Path("scripts/agent_handoff_ledger.py")
content = p.read_text()

target = 'changed = sorted(field for field in RECORD_FIELDS if bundle["record"][field] != record[field])'
repl = 'changed = sorted(field for field in RECORD_FIELDS if bundle["record"].get(field) != record.get(field))'

if target in content:
    content = content.replace(target, repl)
    p.write_text(content)
    print("SUCCESS")
else:
    print("WARNING: target not found")
