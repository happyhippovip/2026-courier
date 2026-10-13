import os
import time
import shutil
from pathlib import Path

def sweep_unowned_artifacts_and_temps(home_dir: str, active_task_ids: set[str], max_age_seconds: float = 86400):
    """
    Periodically sweep the host for unowned artifacts, temporary files, 
    and dangling network handles left by tasks that crashed harder than 
    the recovery pipeline could intercept.
    """
    home = Path(home_dir)
    if not home.exists():
        return 0

    reclaimed_bytes = 0
    now = time.time()

    # 1. Sweep artifacts
    artifacts_dir = home / "artifacts"
    if artifacts_dir.exists():
        for dispatch_dir in artifacts_dir.iterdir():
            if not dispatch_dir.is_dir():
                continue
            
            # The directory name is usually the dispatch_id or task_id.
            # We assume active_task_ids contains the task IDs. In some contexts 
            # dispatch_id is used. We will rely on max_age_seconds for safety 
            # if the ID doesn't directly match, but ideally we match ID.
            task_id = dispatch_dir.name
            if task_id in active_task_ids:
                continue

            mtime = dispatch_dir.stat().st_mtime
            if now - mtime > max_age_seconds:
                for root, _, files in os.walk(dispatch_dir):
                    for f in files:
                        try:
                            reclaimed_bytes += os.path.getsize(os.path.join(root, f))
                        except OSError:
                            pass
                try:
                    shutil.rmtree(dispatch_dir)
                except OSError:
                    pass

    # 2. Sweep temporary stdio files in run_dir
    run_dir = home / "run"
    if run_dir.exists():
        for tmp_file in run_dir.glob("task-*.out"):
            mtime = tmp_file.stat().st_mtime
            if now - mtime > max_age_seconds:
                try:
                    reclaimed_bytes += tmp_file.stat().st_size
                    tmp_file.unlink()
                except OSError:
                    pass
        for tmp_file in run_dir.glob("task-*.err"):
            mtime = tmp_file.stat().st_mtime
            if now - mtime > max_age_seconds:
                try:
                    reclaimed_bytes += tmp_file.stat().st_size
                    tmp_file.unlink()
                except OSError:
                    pass

    return reclaimed_bytes
