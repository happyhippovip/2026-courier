#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import requests
import json
import threading

def log(msg):
    print(f"[Soak Test] {msg}", flush=True)

def submit_goals(count):
    env = os.environ.copy()
    for i in range(count):
        cmd = ["python3", "tools/courierctl/courierctl.py", "--json", "submit", f"Soak test goal {i}"]
        res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60)
        if res.returncode != 0:
            log(f"Failed to submit goal {i}: {res.stderr}")
        time.sleep(0.5)

def run_soak():
    log("Starting Soak Test...")
    submit_goals(50)
    log("Submitted 50 goals.")
    
    # Wait and monitor
    start = time.time()
    while time.time() - start < 300:
        res = subprocess.run(["python3", "tools/courierctl/courierctl.py", "status"], env=os.environ.copy(), capture_output=True, text=True)
        log(res.stdout.replace('\n', ' '))
        time.sleep(30)
    
    log("Soak test complete.")

if __name__ == "__main__":
    run_soak()
