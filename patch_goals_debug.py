import os
from pathlib import Path

app_file = Path("server/app.py")
content = app_file.read_text()

content = content.replace('if not _worker_is_eligible(state, candidate, worker_id):', '''print(f"DEBUG: checking candidate {candidate.get('task_id')} status {candidate.get('status')} for worker {worker_id}", flush=True)
                if not _worker_is_eligible(state, candidate, worker_id):
                    print(f"DEBUG: worker {worker_id} NOT eligible for {candidate.get('task_id')}", flush=True)''')

app_file.write_text(content)
