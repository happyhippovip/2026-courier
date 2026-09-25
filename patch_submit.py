import re
from pathlib import Path

p = Path("server/app.py")
content = p.read_text()

target_submit = '        "terminal": data.get("terminal", True)\n    }'
repl_submit = '        "terminal": data.get("terminal", True),\n        "community_id": data.get("community_id", "public")\n    }'
content = content.replace(target_submit, repl_submit)

p.write_text(content)
print("SUCCESS")
