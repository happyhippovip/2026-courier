#!/usr/bin/env python3
import os
import sys
import time
import requests

# 5 minutes without heartbeat means worker is stale
STALE_THRESHOLD_SECONDS = 300


def log(msg):
    print(f"[Watchdog] {msg}", flush=True)


def resolve_api_key():
    api_key = os.environ.get("COURIER_API_KEY")
    if not api_key:
        try:
            import keyring
            api_key = (
                keyring.get_password("courier_worker", "courier_api_key")
                or keyring.get_password("courier_worker", "COURIER_API_KEY")
            )
        except Exception:
            pass
    return api_key


def resolve_api_url():
    return os.environ.get("COURIER_SERVER", "http://127.0.0.1:8080").rstrip("/")


def check_and_reclaim(api_url=None, api_key=None, timeout=10):
    url = api_url or resolve_api_url()
    key = api_key or resolve_api_key()
    if not key:
        raise SystemExit("COURIER_API_KEY is required")

    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        res = requests.post(f"{url}/tasks/reclaim_stale", headers=headers, timeout=timeout)
        if res.status_code == 200:
            data = res.json()
            reclaimed = data.get("reclaimed_tasks", 0)
            quarantined = data.get("quarantined_tasks", 0)
            if reclaimed > 0:
                log(f"Reclaimed {reclaimed} tasks from stale workers.")
            if quarantined > 0:
                log(f"Quarantined {quarantined} tasks with ambiguous post-crash effects.")
            return {"status_code": 200, "reclaimed_tasks": reclaimed, "quarantined_tasks": quarantined}
        else:
            log(f"Server returned HTTP {res.status_code}")
            return {"status_code": res.status_code, "reclaimed_tasks": 0, "quarantined_tasks": 0}
    except Exception as e:
        log(f"Error calling watchdog endpoint: {e}")
        return {"status_code": None, "error": str(e), "reclaimed_tasks": 0, "quarantined_tasks": 0}


def run_loop(interval=60):
    api_key = resolve_api_key()
    api_url = resolve_api_url()
    if not api_key:
        raise SystemExit("COURIER_API_KEY is required")
    log(f"Starting Courier Watchdog pointing to {api_url}")
    while True:
        check_and_reclaim(api_url=api_url, api_key=api_key)
        time.sleep(interval)


if __name__ == "__main__":
    run_loop()
