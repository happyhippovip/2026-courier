import re
from pathlib import Path

p = Path("server/app.py")
content = p.read_text()

target = '        profiles_dict[id] = data.get("custom_profile", profiles_dict.get(id, {}))\n        return jsonify({"status": "UPDATED", "profile": profiles_dict[id]})'
repl = '        profiles_dict[id] = data.get("custom_profile", profiles_dict.get(id, {}))\n        save_state(state)\n        return jsonify({"status": "UPDATED", "profile": profiles_dict[id]})'

content = content.replace(target, repl)

p.write_text(content)
print("SUCCESS")
