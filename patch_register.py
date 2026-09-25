import re
from pathlib import Path

p = Path("server/app.py")
content = p.read_text()

target_cap = '    capabilities = _string_list(data.get("capabilities", existing.get("capabilities", [])))'
repl_cap = """    capabilities = _string_list(data.get("capabilities", existing.get("capabilities", [])))
    groups = _string_list(data.get("groups", existing.get("groups", [])))
    community_id = data.get("community_id", existing.get("community_id", "public"))
"""
content = content.replace(target_cap, repl_cap)

target_dict = '        "cost_class": data.get("cost_class", "unknown")\n    }'
repl_dict = '        "cost_class": data.get("cost_class", "unknown"),\n        "groups": groups or [],\n        "community_id": community_id\n    }'
content = content.replace(target_dict, repl_dict)

p.write_text(content)
print("SUCCESS")
