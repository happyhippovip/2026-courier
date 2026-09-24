#!/usr/bin/env python3
import glob
import os
import time


def _safe_remove(filepath):
    """Safely attempt to remove a file, returning True if deleted, False if skipped/locked."""
    try:
        os.remove(filepath)
        print(f"Removed log: {filepath}")
        return True
    except (PermissionError, OSError) as e:
        print(f"Skipping locked or inaccessible log: {filepath} ({e})")
        return False


def _safe_stat_mtime(filepath):
    try:
        return os.stat(filepath).st_mtime
    except (FileNotFoundError, OSError):
        return 0.0


def rotate_logs(log_dir="logs", max_files=10, max_age_days=7, max_bytes=None):
    """
    Implements bounded, Windows-resilient log rotation.
    - Deletes log files older than max_age_days.
    - Keeps at most max_files, deleting oldest first.
    - Gracefully handles locked files on Windows (WinError 32 / PermissionError).
    - If max_bytes is specified, rotates oversized files.
    """
    if not os.path.exists(log_dir):
        return {"removed": 0, "skipped_locked": 0}

    log_files = glob.glob(os.path.join(log_dir, "*.log"))
    now = time.time()
    removed_count = 0
    skipped_count = 0

    # 1. Delete files older than max_age_days
    for f in log_files:
        mtime = _safe_stat_mtime(f)
        if mtime > 0 and mtime < now - (max_age_days * 86400):
            if _safe_remove(f):
                removed_count += 1
            else:
                skipped_count += 1

    # Refresh log list
    log_files = glob.glob(os.path.join(log_dir, "*.log"))

    # 2. Keep only max_files
    if len(log_files) > max_files:
        # Sort by modification time (oldest first)
        log_files.sort(key=_safe_stat_mtime)
        files_to_delete = len(log_files) - max_files
        for f in log_files[:files_to_delete]:
            if _safe_remove(f):
                removed_count += 1
            else:
                skipped_count += 1

    # 3. Optional size bounding: if max_bytes specified and file exceeds it
    if max_bytes is not None and max_bytes > 0:
        log_files = glob.glob(os.path.join(log_dir, "*.log"))
        for f in log_files:
            try:
                if os.path.getsize(f) > max_bytes:
                    backup = f + ".1"
                    try:
                        if os.path.exists(backup):
                            _safe_remove(backup)
                        os.replace(f, backup)
                        print(f"Rotated oversized log: {f} -> {backup}")
                    except (PermissionError, OSError) as e:
                        print(f"Could not rotate locked oversized log: {f} ({e})")
            except (FileNotFoundError, OSError):
                pass

    return {"removed": removed_count, "skipped_locked": skipped_count}


if __name__ == "__main__":
    rotate_logs()
