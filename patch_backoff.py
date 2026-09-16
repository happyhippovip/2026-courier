import re
import os

def patch_file(path):
    with open(path, 'r') as f:
        c = f.read()

    # Add error_backoff tracking
    if "error_backoff = 2" not in c:
        if "registered = False" in c:
            c = c.replace("registered = False\n    ", "registered = False\n    error_backoff = 2\n    ")
            c = c.replace("registered = False\n        ", "registered = False\n        error_backoff = 2\n        ")
        
        # Replace time.sleep(5) after network errors with exponential backoff + jitter
        import re
        c = re.sub(r'time\.sleep\(5\)\s*# backoff', r'time.sleep(error_backoff + __import__("random").uniform(0, 2))\n                    error_backoff = min(60, error_backoff * 2)', c)
        
        c = re.sub(r'time\.sleep\(5\)\s*continue', r'time.sleep(error_backoff + __import__("random").uniform(0, 2))\n                    error_backoff = min(60, error_backoff * 2)\n                    continue', c)
        
        # On success reset error_backoff
        c = c.replace("registered = True", "registered = True\n                error_backoff = 2")
        c = c.replace("task = res.get(\"task\")", "task = res.get(\"task\")\n                error_backoff = 2")
        c = c.replace('res, err = http_post(config, "/workers/heartbeat", payload_hb)\n            if err:', 'res, err = http_post(config, "/workers/heartbeat", payload_hb)\n            if err:')

    with open(path, 'w') as f:
        f.write(c)

patch_file("scripts/mac_worker/daemon.py")
patch_file("scripts/revenue_worker_adapter.py")
patch_file("scripts/courier_github_dispatcher.py")
