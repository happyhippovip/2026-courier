import os
from pathlib import Path

app_file = Path("server/app.py")
content = app_file.read_text()

content = content.replace('''    elif not _legacy_target_matches(task, worker):
        return False
        
    return _resources_available(state, task)''',
'''    elif not _legacy_target_matches(task, worker):
        return False
        
    if not set(required_authorities).issubset(set(worker_authorities)):
        return False
        
    return _resources_available(state, task)''')

app_file.write_text(content)
