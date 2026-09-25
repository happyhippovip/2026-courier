from pathlib import Path

p = Path("scripts/agent_handoff_ledger.py")
content = p.read_text()

target = """                if previous_record[field] != entry["record"][field]"""
repl = """                if previous_record.get(field) != entry["record"].get(field)"""

if target in content:
    content = content.replace(target, repl)
    print("SUCCESS")
else:
    print("WARNING: target not found")

p.write_text(content)
