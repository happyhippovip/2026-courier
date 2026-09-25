import os
from pathlib import Path

app_file = Path("server/app.py")
content = app_file.read_text()

content = content.replace('''            else:
                save_state(state)
                return jsonify({"task": None, "reason": "WORKER_BUSY"})''',
'''            else:
                worker["available"] = False
                save_state(state)
                return jsonify({"task": task})''')

app_file.write_text(content)
