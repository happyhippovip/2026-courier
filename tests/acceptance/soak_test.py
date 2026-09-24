#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
COURIERCTL_PATH = REPO_ROOT / "tools" / "courierctl" / "courierctl.py"


def log(msg):
    print(f"[Soak Test] {msg}", flush=True)


def submit_goals(count):
    env = os.environ.copy()
    sleep_delay = float(os.environ.get("COURIER_SOAK_DELAY", "0.5"))
    for i in range(count):
        cmd = [sys.executable, str(COURIERCTL_PATH), "--json", "submit", f"Soak test goal {i}"]
        res = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if res.returncode != 0:
            log(f"Failed to submit goal {i}: {res.stderr}")
        if sleep_delay > 0:
            time.sleep(sleep_delay)


def run_soak():
    log("Starting Soak Test...")
    count = int(os.environ.get("COURIER_SOAK_COUNT", "50"))
    duration = int(os.environ.get("COURIER_SOAK_DURATION", "300"))
    interval = float(os.environ.get("COURIER_SOAK_INTERVAL", "30"))

    submit_goals(count)
    log(f"Submitted {count} goals.")

    # Wait and monitor
    start = time.time()
    while time.time() - start < duration:
        res = subprocess.run(
            [sys.executable, str(COURIERCTL_PATH), "status"],
            env=os.environ.copy(),
            capture_output=True,
            text=True,
        )
        log(res.stdout.replace("\n", " "))
        if duration > 0 and interval > 0:
            time.sleep(interval)

    log("Soak test complete.")


if __name__ == "__main__":
    run_soak()
