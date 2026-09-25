from pathlib import Path

p = Path("scripts/agent_handoff_ledger.py")
content = p.read_text()

target = """    for field in RECORD_FIELDS:
        value = record[field]"""

repl = """    for field in RECORD_FIELDS:
        if field not in record:
            continue
        value = record[field]"""

if target in content:
    content = content.replace(target, repl)
    print("SUCCESS")
else:
    print("WARNING: target not found")

p.write_text(content)
