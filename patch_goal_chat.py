import re
from pathlib import Path

p = Path("server/app.py")
content = p.read_text()

target = '        chat_history.append(chat_message)\n        return jsonify({"status": "POSTED", "message": chat_message})'
repl = '        chat_history.append(chat_message)\n        save_state(state)\n        return jsonify({"status": "POSTED", "message": chat_message})'

content = content.replace(target, repl)

p.write_text(content)
print("SUCCESS")
