import os
from pathlib import Path

app_file = Path("server/app.py")
content = app_file.read_text()

old = """                if not _worker_is_eligible(state, candidate, worker_id):
                    print(f"DEBUG: worker {worker_id} NOT eligible for {candidate.get('task_id')}", flush=True)
                    continue
                    continue
                if _cheaper_eligible_worker_exists(state, candidate, worker_id):
                    continue
                    continue"""

new = """                if not _worker_is_eligible(state, candidate, worker_id):
                    continue
                if _cheaper_eligible_worker_exists(state, candidate, worker_id):
                    continue"""

content = content.replace(old, new)
app_file.write_text(content)
