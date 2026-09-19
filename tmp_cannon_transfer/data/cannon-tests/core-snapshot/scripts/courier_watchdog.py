#!/usr/bin/env python3
import os
import sys
import time
import requests
from scripts.redaction import get_secret, apply_redaction

API_URL = os.environ.get("COURIER_SERVER", "http://127.0.0.1:8080").rstrip("/")
API_KEY = get_secret("api_key")

apply_redaction([API_KEY])
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# 5 minutes without heartbeat means worker is stale
STALE_THRESHOLD_SECONDS = 300 

def log(msg):
    print(f"[Watchdog] {msg}", flush=True)

def run_loop():
    if not API_KEY:
        raise SystemExit("COURIER_API_KEY is required")
    log(f"Starting Courier Watchdog pointing to {API_URL}")
    while True:
        try:
            # We need to know which tasks are stuck.
            # We can trigger a new endpoint /system/reclaim_stale or just let the watchdog do it.
            # But the watchdog doesn't have direct access to state! It must use HTTP.
            # Let's add an endpoint to the server: POST /tasks/reclaim_stale
            res = requests.post(f"{API_URL}/tasks/reclaim_stale", headers=HEADERS, timeout=10)
            if res.status_code == 200:
                data = res.json()
                reclaimed = data.get("reclaimed_tasks", 0)
                quarantined = data.get("quarantined_tasks", 0)
                if reclaimed > 0:
                    log(f"Reclaimed {reclaimed} tasks from stale workers.")
                if quarantined > 0:
                    log(f"Quarantined {quarantined} tasks with ambiguous post-crash effects.")
        except Exception as e:
            log(f"Error calling watchdog endpoint: {e}")
            
        time.sleep(60)

from scripts.mutex import enforce_single_instance

if __name__ == "__main__":
    enforce_single_instance("Global\\CourierWatchdog")
    run_loop()
