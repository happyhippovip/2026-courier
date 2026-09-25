import os
from pathlib import Path

app_file = Path("server/app.py")
content = app_file.read_text()

content = content.replace('if time.time() <= state.get("provider_locks", {}).get(lock_key, 0):', '''print(f"DEBUG: checking lock_key {lock_key}, val {state.get('provider_locks', {}).get(lock_key, 0)} vs time {time.time()}", flush=True)
    if time.time() <= state.get("provider_locks", {}).get(lock_key, 0):''')
app_file.write_text(content)
