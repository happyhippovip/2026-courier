from pathlib import Path
import re

p = Path("scripts/agent_handoff_ledger.py")
content = p.read_text()

# Add to RECORD_FIELDS
if '"RUNNING_TASKS",' not in content:
    content = content.replace('"TOMBSTONED_EDGES",', '"TOMBSTONED_EDGES",\n    "RUNNING_TASKS",')

# Add to DICT_FIELDS
if '"RUNNING_TASKS",' not in content.split("DICT_FIELDS = {")[1].split("}")[0]:
    content = content.replace('DICT_FIELDS = {', 'DICT_FIELDS = {\n    "RUNNING_TASKS",')

# Update backward compat
old_compat = 'all(m in ["TASK_SPECS", "TOMBSTONED_EDGES"] for m in missing)'
new_compat = 'all(m in ["TASK_SPECS", "TOMBSTONED_EDGES", "RUNNING_TASKS"] for m in missing)'
if old_compat in content:
    content = content.replace(old_compat, new_compat)
    
old_compat2 = 'f not in ["TASK_SPECS", "TOMBSTONED_EDGES"]'
new_compat2 = 'f not in ["TASK_SPECS", "TOMBSTONED_EDGES", "RUNNING_TASKS"]'
if old_compat2 in content:
    content = content.replace(old_compat2, new_compat2)

# Update default init
old_default = '    if "TOMBSTONED_EDGES" not in record:\n        record["TOMBSTONED_EDGES"] = []'
new_default = '    if "TOMBSTONED_EDGES" not in record:\n        record["TOMBSTONED_EDGES"] = []\n    if "RUNNING_TASKS" not in record:\n        record["RUNNING_TASKS"] = {}'
if old_default in content:
    content = content.replace(old_default, new_default)

p.write_text(content)
print("SUCCESS")
