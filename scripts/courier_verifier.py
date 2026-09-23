#!/usr/bin/env python3
import os
import sys
import time
import requests
import hashlib

def get_server_url():
    url = os.environ.get("COURIER_SERVER")
    if not url:
        try:
            import keyring
            url = keyring.get_password("courier_worker", "courier_server_url")
        except Exception:
            url = None
    return (url or "http://127.0.0.1:8080").rstrip("/")

def get_api_key():
    key = os.environ.get("COURIER_VERIFIER_API_KEY")
    if not key:
        try:
            import keyring
            key = keyring.get_password("courier_worker", "courier_verifier_api_key")
        except Exception:
            key = None
    return key

def get_headers():
    key = get_api_key()
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

API_URL = get_server_url()
API_KEY = get_api_key()
HEADERS = get_headers()
VERIFIER_ID = os.environ.get("COURIER_VERIFIER_ID", "VERIFIER-01")

def log(msg):
    print(f"[Verifier] {msg}", flush=True)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def verify_artifact(path, expected_hash):
    if not path or not isinstance(path, (str, os.PathLike)):
        log(f"Artifact path invalid: {path!r}")
        return False
    path_str = str(path).strip()
    if not path_str:
        log("Artifact path is empty")
        return False
    # Try CWD first, then repo root as fallback (verifier CWD may differ from worker CWD)
    candidates = [path_str]
    if not os.path.isabs(path_str):
        candidates.append(os.path.join(REPO_ROOT, path_str))
    resolved = None
    for c in candidates:
        if os.path.exists(c) and os.path.isfile(c):
            resolved = c
            break
    if resolved is None:
        log(f"Artifact missing: {path_str} (checked: {candidates})")
        return False
    if not expected_hash:
        return True
    h = hashlib.sha256()
    try:
        with open(resolved, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                h.update(chunk)
        actual_hash = h.hexdigest()
        if actual_hash.lower() == str(expected_hash).strip().lower():
            return True
        else:
            log(f"Hash mismatch for {resolved}. Expected {expected_hash}, got {actual_hash}")
            return False
    except Exception as e:
        log(f"Error reading artifact {resolved}: {e}")
        return False

def run_loop():
    api_key = get_api_key()
    if not api_key:
        raise SystemExit("COURIER_VERIFIER_API_KEY is required")
    api_url = get_server_url()
    verifier_id = os.environ.get("COURIER_VERIFIER_ID", VERIFIER_ID)
    log(f"Starting Courier Verifier ({verifier_id}) pointing to {api_url}")
    while True:
        try:
            headers = get_headers()
            res = requests.get(f"{api_url}/tasks/pending_verification", headers=headers, timeout=10)
            if res.status_code == 200:
                tasks = res.json().get("tasks", [])
                for task in tasks:
                    task_id = task.get("task_id")
                    result = task.get("result", {})
                    result_id = result.get("result_id")
                    artifacts = result.get("artifacts", [])
                    
                    log(f"Verifying task {task_id} (result {result_id})...")
                    
                    verdict = "PASS"
                    reason = None
                    if "revenue_safety_audit" in task.get("capabilities", []):
                        log(f"Running deterministic revenue verification for {task_id}...")
                        import tempfile, json, subprocess
                        with tempfile.TemporaryDirectory() as td:
                            task_file = os.path.join(td, "task.json")
                            candidate_file = os.path.join(td, "candidate.json")
                            with open(task_file, "w") as f:
                                json.dump(task, f)
                            with open(candidate_file, "w") as f:
                                json.dump(result.get("result_data", {}), f)
                            
                            cmd = [sys.executable, os.path.join(os.path.dirname(__file__), "revenue_v1_safety_baseline.py"), "verify", task_file, td, candidate_file]
                            try:
                                subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=60)
                                verdict = "PASS"
                            except subprocess.CalledProcessError as e:
                                log(f"Revenue verification failed: {e.output.decode('utf-8', errors='ignore')}")
                                verdict = "FAIL"
                                reason = "REVENUE_AUDIT_FAILED"
                            except subprocess.TimeoutExpired:
                                log("Revenue verification timed out after 60s")
                                verdict = "FAIL"
                                reason = "REVENUE_AUDIT_TIMEOUT"
                    else:
                        if not isinstance(artifacts, list):
                            verdict = "FAIL"
                            reason = "MALFORMED_ARTIFACTS_LIST"
                        else:
                            for art in artifacts:
                                if isinstance(art, dict):
                                    path = art.get("path")
                                    expected_hash = art.get("sha256")
                                elif isinstance(art, (str, os.PathLike)):
                                    path = art
                                    expected_hash = None
                                else:
                                    verdict = "FAIL"
                                    reason = f"INVALID_ARTIFACT_ENTRY: {art!r}"
                                    break
                                
                                if not verify_artifact(path, expected_hash):
                                    verdict = "FAIL"
                                    reason = f"ARTIFACT_VERIFICATION_FAILED: {path}"
                                    break
                            
                    verify_payload = {
                        "task_id": task_id,
                        "verifier_id": verifier_id,
                        "received_runtime_identity": task.get("server_binding"),
                        "result_id": result_id,
                        "verdict": verdict,
                        "artifacts": artifacts
                    }
                    if reason:
                        verify_payload["reason"] = reason
                    vr = requests.post(f"{api_url}/tasks/verify", json=verify_payload, headers=headers, timeout=10)
                    if vr.status_code == 200:
                        log(f"Successfully verified {task_id} with verdict {verdict}")
                    else:
                        log(f"Failed to submit verification for {task_id}: HTTP {vr.status_code} {vr.text}")
        except Exception as e:
            log(f"Error polling for tasks: {e}")
            
        try:
            poll_interval = float(os.environ.get("COURIER_VERIFIER_POLL_INTERVAL", "5.0"))
        except (ValueError, TypeError):
            poll_interval = 5.0

        sleep_time = min(0.2, poll_interval) if ('tasks' in locals() and tasks) else poll_interval
        time.sleep(sleep_time)

if __name__ == "__main__":
    run_loop()
