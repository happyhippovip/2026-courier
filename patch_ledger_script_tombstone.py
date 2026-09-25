from pathlib import Path
import re

p = Path("scripts/agent_handoff_ledger.py")
content = p.read_text()

# Add to RECORD_FIELDS
if '"TOMBSTONED_EDGES",' not in content:
    content = content.replace('"UNPROVEN_EDGES",', '"UNPROVEN_EDGES",\n    "TOMBSTONED_EDGES",')

# Add to LIST_FIELDS
if '"TOMBSTONED_EDGES",' not in content.split("LIST_FIELDS = {")[1].split("}")[0]:
    content = content.replace('LIST_FIELDS = {', 'LIST_FIELDS = {\n    "TOMBSTONED_EDGES",')

# Update backwards compatibility in validate_record
old_compat = 'if missing == ["TASK_SPECS"] and not extra:'
new_compat = 'if all(m in ["TASK_SPECS", "TOMBSTONED_EDGES"] for m in missing) and not extra:'
if old_compat in content:
    content = content.replace(old_compat, new_compat)

# Default value
old_default = 'if "TASK_SPECS" not in record:\n        record["TASK_SPECS"] = {}'
new_default = 'if "TASK_SPECS" not in record:\n        record["TASK_SPECS"] = {}\n    if "TOMBSTONED_EDGES" not in record:\n        record["TOMBSTONED_EDGES"] = []'
if old_default in content:
    content = content.replace(old_default, new_default)

# Edge Conservation logic
old_edge = 'old_all_edges = set(bundle["record"].get("UNPROVEN_EDGES", [])) | set(bundle["record"].get("PROVEN_EDGES", []))'
new_edge = 'old_all_edges = set(bundle["record"].get("UNPROVEN_EDGES", [])) | set(bundle["record"].get("PROVEN_EDGES", [])) | set(bundle["record"].get("TOMBSTONED_EDGES", []))'
if old_edge in content:
    content = content.replace(old_edge, new_edge)

old_edge_2 = 'new_all_edges = set(record.get("UNPROVEN_EDGES", [])) | set(record.get("PROVEN_EDGES", []))'
new_edge_2 = 'new_all_edges = set(record.get("UNPROVEN_EDGES", [])) | set(record.get("PROVEN_EDGES", [])) | set(record.get("TOMBSTONED_EDGES", []))'
if old_edge_2 in content:
    content = content.replace(old_edge_2, new_edge_2)

# Update tombstone command
old_tombstone = """            unproven.remove(args.edge)
            record["UNPROVEN_EDGES"] = unproven"""
new_tombstone = """            unproven.remove(args.edge)
            record["UNPROVEN_EDGES"] = unproven
            tombstoned = record.get("TOMBSTONED_EDGES", [])
            tombstoned.append(args.edge)
            record["TOMBSTONED_EDGES"] = tombstoned"""
if old_tombstone in content:
    content = content.replace(old_tombstone, new_tombstone)

p.write_text(content)
print("SUCCESS")
