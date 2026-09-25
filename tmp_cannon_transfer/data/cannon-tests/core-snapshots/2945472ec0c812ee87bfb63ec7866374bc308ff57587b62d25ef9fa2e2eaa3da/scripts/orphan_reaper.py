import os
import time
import tempfile
import psutil
from pathlib import Path

def reap_orphans():
    print("Starting orphan reaper...")
    killed = 0
    
    # 1. Kill stale process trees that are OWNED by Courier
    # We query the local DB for processes we launched.
    db_path = Path(__file__).parent / 'windows_worker' / 'state' / 'queue.db'
    if db_path.exists():
        import sqlite3
        with sqlite3.connect(db_path) as c:
            c.row_factory = sqlite3.Row
            cursor = c.execute("SELECT job_id, pid, create_time, executable FROM background_jobs WHERE status = 'RUNNING' AND (julianday('now') - julianday(started_at)) * 24 * 60 * 60 > 3600")
            for row in cursor.fetchall():
                try:
                    proc = psutil.Process(row['pid'])
                    # Verify exact ownership
                    if abs(proc.create_time() - row['create_time']) < 5.0:
                        print(f"Reaping owned Courier job: {row['executable']} (PID: {proc.pid})")
                        for child in proc.children(recursive=True):
                            child.kill()
                        proc.kill()
                        killed += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, ValueError, TypeError):
                    pass
            
    # 2. Cleanup stale temp files from runner.py
    temp_dir = Path(tempfile.gettempdir())
    cleaned = 0
    now = time.time()
    for f in temp_dir.glob('tmp*.out'):
        if f.is_file() and now - f.stat().st_mtime > 86400: # 24 hours
            try:
                f.unlink()
                cleaned += 1
            except Exception:
                pass
    for f in temp_dir.glob('tmp*.err'):
        if f.is_file() and now - f.stat().st_mtime > 86400:
            try:
                f.unlink()
                cleaned += 1
            except Exception:
                pass
                
    print(f"Reaper finished. Killed {killed} processes, cleaned {cleaned} temp files.")

if __name__ == '__main__':
    reap_orphans()
