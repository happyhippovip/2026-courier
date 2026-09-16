#!/usr/bin/env python3
import os
import sys
import time
import requests
import hashlib

API_URL = os.environ.get("COURIER_SERVER", "http://127.0.0.1:8080").rstrip("/")
API_KEY = os.environ.get("COURIER_API_KEY")
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
VERIFIER_ID = "VERIFIER-01"

def log(msg):
    print(f"[Verifier] {msg}", flush=True)

def verify_artifact(path, expected_hash):
    if not os.path.exists(path):
        log(f"Artifact missing: {path}")
        return False
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                h.update(chunk)
        actual_hash = h.hexdigest()
        if actual_hash == expected_hash:
            return True
        else:
            log(f"Hash mismatch for {path}. Expected {expected_hash}, got {actual_hash}")
            return False
    except Exception as e:
        log(f"Error reading artifact {path}: {e}")
        return False

def run_loop():
    if not API_KEY:
        raise SystemExit("COURIER_API_KEY is required")
    log(f"Starting Courier Verifier ({VERIFIER_ID}) pointing to {API_URL}")
    while True:
        try:
            res = requests.get(f"{API_URL}/tasks/pending_verification", headers=HEADERS, timeout=10)
            if res.status_code == 200:
                tasks = res.json().get("tasks", [])
                for task in tasks:
                    task_id = task.get("task_id")
                    result = task.get("result", {})
                    result_id = result.get("result_id")
                    artifacts = result.get("artifacts", [])
                    
                    log(f"Verifying task {task_id} (result {result_id})...")
                    
                    verdict = "PASS"
                    for art in artifacts:
                        path = art.get("path")
                        expected_hash = art.get("sha256")
                        if not verify_artifact(path, expected_hash):
                            verdict = "FAIL"
                            break
                            
                    verify_payload = {
                        "task_id": task_id,
                        "verifier_id": VERIFIER_ID,
                        "result_id": result_id,
                        "verdict": verdict,
                        "artifacts": artifacts
                    }
                    vr = requests.post(f"{API_URL}/tasks/verify", json=verify_payload, headers=HEADERS, timeout=10)
                    if vr.status_code == 200:
                        log(f"Successfully verified {task_id} with verdict {verdict}")
                    else:
                        log(f"Failed to submit verification for {task_id}: HTTP {vr.status_code} {vr.text}")
        except Exception as e:
            log(f"Error polling for tasks: {e}")
            
        time.sleep(5)

if __name__ == "__main__":
    run_loop()
