import os
from pathlib import Path

def patch_log(file_path):
    with open(file_path, "r") as f:
        c = f.read()

    new_log = """
def write_log(msg):
    print(msg)
    log_file = LOGS_DIR / "worker.log"
    # S04: Bounded logs
    if log_file.exists() and log_file.stat().st_size > 5 * 1024 * 1024:
        try:
            with open(log_file, "r") as f:
                content = f.read()
            with open(log_file, "w") as f:
                f.write(content[-2 * 1024 * 1024:]) # Keep last 2MB
        except Exception:
            pass
    with open(log_file, "a") as f:
        import time
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\\n")
"""

    if "def write_log(msg):" in c:
        # Find the end of write_log (assuming it ends with f.write...)
        start_idx = c.find("def write_log(msg):")
        end_idx = c.find("def", start_idx + 10)
        
        # In revenue_worker_adapter.log it's revenue_worker.log not worker.log
        if "revenue_worker" in file_path:
            new_log = new_log.replace("worker.log", "revenue_worker.log")
            
        c = c[:start_idx] + new_log.strip() + "\n\n" + c[end_idx:]
        with open(file_path, "w") as f:
            f.write(c)

patch_log("scripts/mac_worker/daemon.py")
patch_log("scripts/revenue_worker_adapter.py")
