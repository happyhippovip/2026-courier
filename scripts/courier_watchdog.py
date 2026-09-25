#!/usr/bin/env python3
import os
import sys
import time
import requests

API_URL = os.environ.get("COURIER_SERVER", "http://127.0.0.1:8080").rstrip("/")
API_KEY = os.environ.get("COURIER_API_KEY")
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# 5 minutes without heartbeat means worker is stale
STALE_THRESHOLD_SECONDS = 300 

def log(msg):
    print(f"[Watchdog] {msg}", flush=True)

def run_once():
    """One reclaim poll. Returns (reclaimed, quarantined). Never raises."""
    try:
        # The watchdog has no direct state access; it must use HTTP.
        res = requests.post(f"{API_URL}/tasks/reclaim_stale", headers=HEADERS, timeout=10)
        if res.status_code == 200:
            data = res.json()
            reclaimed = data.get("reclaimed_tasks", 0)
            quarantined = data.get("quarantined_tasks", 0)
            if reclaimed > 0:
                log(f"Reclaimed {reclaimed} tasks from stale workers.")
            if quarantined > 0:
                log(f"Quarantined {quarantined} tasks with ambiguous post-crash effects.")
            return reclaimed, quarantined
        log(f"Reclaim endpoint returned HTTP {res.status_code}; will retry next poll.")
        return 0, 0
    except Exception as e:
        log(f"Error calling watchdog endpoint: {e}")
        return 0, 0

def run_loop():
    if not API_KEY:
        raise SystemExit("COURIER_API_KEY is required")
    log(f"Starting Courier Watchdog pointing to {API_URL}")
    while True:
        run_once()
        time.sleep(60)

if __name__ == "__main__":
    run_loop()
