import os

def refine_daemon():
    with open("scripts/mac_worker/daemon.py", "r") as f:
        c = f.read()
    
    # Just replace all `time.sleep(5)` that are preceded by `if err:` inside the loop
    # with a smart jitter sleep.
    if "import random" not in c:
        c = c.replace("import sys", "import sys\nimport random")
    
    c = c.replace("time.sleep(5) # backoff", "time.sleep(error_backoff + random.uniform(0, 2))\n                    error_backoff = min(60, error_backoff * 2)")
    
    # Fix heartbeat sleep
    c = c.replace("""            if err:
                write_log(f"Heartbeat failed: {err}")
                registered = False
                time.sleep(5)
                continue""", """            if err:
                write_log(f"Heartbeat failed: {err}")
                registered = False
                time.sleep(error_backoff + random.uniform(0, 2))
                error_backoff = min(60, error_backoff * 2)
                continue""")

    # Fix claim sleep
    c = c.replace("""                if err:
                    write_log(f"Claim failed: {err}")
                    time.sleep(5)
                    continue""", """                if err:
                    write_log(f"Claim failed: {err}")
                    time.sleep(error_backoff + random.uniform(0, 2))
                    error_backoff = min(60, error_backoff * 2)
                    continue""")

    # Add error_backoff initialization
    if "error_backoff = 2" not in c:
        c = c.replace("registered = False", "registered = False\n    error_backoff = 2")
    
    # Add cleanup of old temp directories inside loop
    cleanup_code = """
            # Cleanup old temp dirs
            try:
                import shutil
                paths = [p for p in STATE_DIR.iterdir() if p.is_dir() and p.name.startswith("task_")]
                paths.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                for p in paths[5:]: # Keep last 5
                    shutil.rmtree(p)
            except Exception:
                pass
"""
    if "Cleanup old temp dirs" not in c:
        c = c.replace("registered = True", "registered = True" + cleanup_code)

    with open("scripts/mac_worker/daemon.py", "w") as f:
        f.write(c)

def refine_github():
    with open("scripts/courier_github_dispatcher.py", "r") as f:
        c = f.read()
    
    if "import random" not in c:
        c = c.replace("import time", "import time\nimport random")

    # The loop in github_dispatcher is different. Let's see it.
    with open("scripts/courier_github_dispatcher.py", "w") as f:
        f.write(c)

refine_daemon()
refine_github()
