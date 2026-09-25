import os
from pathlib import Path

app_file = Path("server/app.py")
content = app_file.read_text()

content = content.replace('return jsonify({"task": None, "reason": "PROVIDER_UNAVAILABLE"})', 'print("DEBUG: returned PROVIDER_UNAVAILABLE", flush=True); return jsonify({"task": None, "reason": "PROVIDER_UNAVAILABLE"})')
content = content.replace('return jsonify({"task": None, "reason": "PROVIDER_QUOTA_LOCKED"})', 'print(f"DEBUG: returned PROVIDER_QUOTA_LOCKED for {worker_provider} lock {state.get(\'provider_locks\', {}).get(lock_key, 0)}", flush=True); return jsonify({"task": None, "reason": "PROVIDER_QUOTA_LOCKED"})')
content = content.replace('return jsonify({"task": task})', 'print(f"DEBUG: returning task {task.get(\'task_id\')} from claim_task", flush=True); return jsonify({"task": task})')

app_file.write_text(content)
