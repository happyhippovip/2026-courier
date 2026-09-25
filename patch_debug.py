import os
from pathlib import Path

app_file = Path("server/app.py")
content = app_file.read_text()

content = content.replace('def _worker_is_eligible(state, task, worker_id):', '''def _worker_is_eligible(state, task, worker_id):
    ret = _worker_is_eligible_inner(state, task, worker_id)
    print(f"DEBUG: _worker_is_eligible({task.get('task_id')}, {worker_id}) -> {ret}", flush=True)
    return ret
    
def _worker_is_eligible_inner(state, task, worker_id):''')
app_file.write_text(content)
