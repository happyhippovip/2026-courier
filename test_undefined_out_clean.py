import sys
from scripts.windows_worker.daemon import run_task
try:
    res = run_task({"task_id": "test"}, {"WORKER_ID": "test"})
    print("OK:", res)
except Exception as e:
    print("ERROR:", repr(e))
    sys.exit(1)
