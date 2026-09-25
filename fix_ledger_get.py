from pathlib import Path
import re

p = Path("scripts/agent_handoff_ledger.py")
content = p.read_text()

target = 'set(bundle["record"].get("UNPROVEN_EDGES",\\n    "TOMBSTONED_EDGES", []))'
repl = 'set(bundle["record"].get("UNPROVEN_EDGES", [])) | set(bundle["record"].get("TOMBSTONED_EDGES", []))'
content = re.sub(r'set\(bundle\["record"\]\.get\("UNPROVEN_EDGES",\n\s*"TOMBSTONED_EDGES", \[\]\)\)', repl, content)

target2 = 'set(record.get("UNPROVEN_EDGES",\\n    "TOMBSTONED_EDGES", []))'
repl2 = 'set(record.get("UNPROVEN_EDGES", [])) | set(record.get("TOMBSTONED_EDGES", []))'
content = re.sub(r'set\(record\.get\("UNPROVEN_EDGES",\n\s*"TOMBSTONED_EDGES", \[\]\)\)', repl2, content)

target3 = 'unproven = record.get("UNPROVEN_EDGES",\\n    "TOMBSTONED_EDGES", [])'
repl3 = 'unproven = record.get("UNPROVEN_EDGES", [])'
content = re.sub(r'unproven = record\.get\("UNPROVEN_EDGES",\n\s*"TOMBSTONED_EDGES", \[\]\)', repl3, content)

p.write_text(content)
print("SUCCESS")
