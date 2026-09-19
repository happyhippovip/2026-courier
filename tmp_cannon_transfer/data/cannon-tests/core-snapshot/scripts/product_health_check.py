#!/usr/bin/env python3
import os
import sys
import json
import urllib.request
import urllib.error
import time

def run():
    try:
        import keyring
        API_KEY = os.environ.get("COURIER_API_KEY") or keyring.get_password("courier_worker", "courier_api_key")
    except ImportError:
        API_KEY = os.environ.get("COURIER_API_KEY")

    if not API_KEY:
        print("HUMAN_REQUIRED: No credentials found")
        sys.exit(1)

    API_URL = os.environ.get("COURIER_SERVER", "http://127.0.0.1:8080").rstrip("/")
    headers = {"Authorization": f"Bearer " + API_KEY}

    try:
        req = urllib.request.Request(API_URL + "/status", headers=headers)
        with urllib.request.urlopen(req, timeout=5) as f:
            status = json.loads(f.read().decode("utf-8"))
    except Exception as e:
        print("DEGRADED: Server unreachable or bad credentials: " + str(e))
        sys.exit(1)

    if "goals" not in status or "tasks" not in status:
        print("DEGRADED: Schema incompatible (missing goals/tasks)")
        sys.exit(1)

    try:
        req = urllib.request.Request(API_URL + "/workers", headers=headers)
        with urllib.request.urlopen(req, timeout=5) as f:
            workers = json.loads(f.read().decode("utf-8"))
    except Exception as e:
        print("DEGRADED: Workers endpoint failed: " + str(e))
        sys.exit(1)

    now = time.time()
    verifier_found = False
    for w_id, w_data in workers.items():
        if "verifier" in w_id.lower():
            verifier_found = True
        hb = w_data.get("last_heartbeat", 0)
        if now - hb > 600:
            print("DEGRADED: Stale ownership / inactive worker " + w_id)
            sys.exit(1)

    if not verifier_found:
        print("DEGRADED: No verifier registered or active")
        # Just warn, depending on strictness
        # sys.exit(1)

    print("HEALTHY")

if __name__ == "__main__":
    run()
