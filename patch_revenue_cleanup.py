import os
with open("scripts/revenue_worker_adapter.py", "r") as f:
    c = f.read()

cleanup_code = """
            try:
                paths = [p for p in STATE_DIR.iterdir() if p.is_dir() and not p.name.startswith(".")]
                paths.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                for p in paths[5:]:
                    shutil.rmtree(p)
            except Exception:
                pass
"""

c = c.replace("error_backoff = 2\n    while True:\n        try:", "error_backoff = 2\n    while True:\n        try:\n" + cleanup_code)

with open("scripts/revenue_worker_adapter.py", "w") as f:
    f.write(c)

