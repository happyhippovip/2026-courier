from pathlib import Path

p = Path("scripts/agent_handoff_ledger.py")
content = p.read_text()

target = """    if "TASK_SPECS" not in record:
        record["TASK_SPECS"] = {}
    if "TOMBSTONED_EDGES" not in record:
        record["TOMBSTONED_EDGES"] = []
    reject_secrets(record)
    for field in RECORD_FIELDS:"""

repl = """    reject_secrets(record)
    for field in RECORD_FIELDS:"""

if target in content:
    content = content.replace(target, repl)
    print("SUCCESS")
else:
    print("WARNING: target not found")

p.write_text(content)
