#!/usr/bin/env python3
import os
import glob
import time

def rotate_logs(log_dir="logs", max_files=10, max_age_days=7):
    """
    Implements bounded log rotation.
    - Deletes log files older than max_age_days.
    - Keeps at most max_files, deleting oldest first.
    """
    if not os.path.exists(log_dir):
        return

    log_files = glob.glob(os.path.join(log_dir, "*.log"))
    now = time.time()
    
    # 1. Delete files older than max_age_days
    for f in log_files:
        try:
            mtime = os.stat(f).st_mtime
        except FileNotFoundError:
            continue  # deleted between glob and stat
        if mtime < now - (max_age_days * 86400):
            try:
                os.remove(f)
                print(f"Removed old log: {f}")
            except FileNotFoundError:
                pass  # already deleted by another process
            
    # Refresh log list
    log_files = glob.glob(os.path.join(log_dir, "*.log"))
    
    # 2. Keep only max_files
    if len(log_files) > max_files:
        # Sort by modification time (oldest first)
        log_files.sort(key=lambda x: os.stat(x).st_mtime if os.path.exists(x) else 0)
        files_to_delete = len(log_files) - max_files
        for f in log_files[:files_to_delete]:
            try:
                os.remove(f)
                print(f"Removed log due to count limit: {f}")
            except FileNotFoundError:
                pass  # already deleted

if __name__ == "__main__":
    rotate_logs()
