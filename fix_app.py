import os
import sys
content = open('server/app.py', 'r').read()
content = content.replace(
    'STATE_FILE = os.environ.get("COURIER_STATE_FILE", os.environ.get('COURIER_STATE_FILE', r'C:\ProgramData\Courier\central_state.json'))',
    'CANONICAL_DIR = os.environ.get("COURIER_DATA_DIR", r"C:\ProgramData\Courier")\nSTATE_FILE = os.environ.get("COURIER_STATE_FILE", os.path.join(CANONICAL_DIR, "central_state.json"))'
)
content = content.replace(
    'BATCH_QUEUE_DIR = "server/state/batches"',
    'BATCH_QUEUE_DIR = os.path.join(CANONICAL_DIR, "batches")'
)
open('server/app.py', 'w').write(content)
