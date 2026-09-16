import os
with open("scripts/github_worker_adapter.py", "r") as f:
    c = f.read()

new_validate = """
    try:
        validate_task(task)
    except ValueError as exc:
        print(f"FAILED_TERMINAL={exc}", file=sys.stderr)
        # S08/S05 Fix: Post terminal failure back so server isn't stuck
        result = {
            "worker_id": task.get("worker_id", "GITHUB-HOSTED"),
            "goal_id": task.get("goal_id", ""),
            "task_id": task.get("task_id", ""),
            "attempt_id": task.get("attempt_id", ""),
            "dispatch_id": task.get("dispatch_id", ""),
            "run_id": "failed-early",
            "result_id": "failed-early",
            "status": "FAILED",
            "artifacts": [],
            "raw_result": {"status": "FAILED", "reason": "VALIDATION_ERROR", "stderr": str(exc)}
        }
        try:
            post_result(result)
        except Exception:
            pass
        return 2
"""

import re
c = re.sub(r'    try:\n        validate_task\(task\)\n    except ValueError as exc:\n        print.*?return 2', new_validate.strip(), c, flags=re.DOTALL)

with open("scripts/github_worker_adapter.py", "w") as f:
    f.write(c)

