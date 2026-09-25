import re
from pathlib import Path

p = Path("server/app.py")
content = p.read_text()

target = '        "community_id": data.get("community_id", "public")\n    }'
repl = '        "community_id": data.get("community_id", "public"),\n        "max_budget_eur": data.get("max_budget_eur", 10.00),\n        "accumulated_cost": 0.0\n    }'

content = content.replace(target, repl)

p.write_text(content)
print("SUCCESS")
