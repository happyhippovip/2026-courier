#!/usr/bin/env python3
import os
import sys
import time
import requests
import hashlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.artifact_store import DEFAULT_MAX_BYTES, is_safe_artifact_name, verify_uploaded_artifact

API_URL = os.environ.get("COURIER_SERVER", "http://127.0.0.1:8080").rstrip("/")
API_KEY = os.environ.get("COURIER_VERIFIER_API_KEY")
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
VERIFIER_ID = "VERIFIER-01"

def log(msg):
    print(f"[Verifier] {msg}", flush=True)

REPO_ROOT = Path(__file__).resolve().parent.parent

def verify_artifact(path, expected_hash, repo_root=None):
    root = Path(repo_root or REPO_ROOT).resolve()
    try:
        p = Path(path)
        full_p = p.resolve() if p.is_absolute() else (root / p).resolve()
        if root not in full_p.parents and full_p != root:
            log(f"Artifact path outside repository boundary: {path}")
            return False
        if not full_p.is_file():
            log(f"Artifact missing: {path}")
            return False
    except Exception as e:
        log(f"Invalid artifact path {path}: {e}")
        return False
    h = hashlib.sha256()
    try:
        with open(full_p, "rb") as f:
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

MAX_ARTIFACT_BYTES = int(os.environ.get("COURIER_ARTIFACT_MAX_BYTES", DEFAULT_MAX_BYTES))
REMOTE_TARGETS = ("mac", "windows")


def fetch_artifact(artifact_id):
    """Return (record, bytes) of the server-side uploaded copy."""
    meta = requests.get(f"{API_URL}/artifacts/{artifact_id}/meta", headers=HEADERS, timeout=10)
    meta.raise_for_status()
    blob = requests.get(f"{API_URL}/artifacts/{artifact_id}", headers=HEADERS, timeout=30)
    blob.raise_for_status()
    if len(blob.content) > MAX_ARTIFACT_BYTES:
        raise ValueError("artifact exceeds size limit")
    return meta.json(), blob.content


def verify_artifacts(task, result, fetch=fetch_artifact, local_verify=None):
    """PASS only if every artifact is independently confirmed.

    Uploaded artifacts are re-hashed from the server copy. Mac/Windows artifacts
    must be uploaded: the verifier never opens a remote worker's local path.
    """
    local_verify = local_verify or verify_artifact
    if not isinstance(result, dict):
        log("Result is not a dict.")
        return "FAIL"
    artifacts = result.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        log("No artifact evidence.")
        return "FAIL"
    expected = task.get("artifacts")
    if expected:
        provided_paths = {art.get("path") for art in artifacts if isinstance(art, dict)}
        for exp in expected:
            if exp not in provided_paths:
                log(f"Expected artifact missing from result: {exp}")
                return "FAIL"
    target = str(task.get("target_capability") or task.get("target_agent") or "").lower()
    remote = any(t in target for t in REMOTE_TARGETS)
    for art in artifacts:
        if not isinstance(art, dict):
            log(f"Artifact entry is not a dict: {art}")
            return "FAIL"
        if "artifact_id" in art:
            try:
                record, data = fetch(art["artifact_id"])
            except Exception as e:
                log(f"Cannot fetch uploaded artifact: {e}")
                return "FAIL"
            ok, reason = verify_uploaded_artifact(data, record, art, task)
            if not ok:
                log(f"Uploaded artifact rejected: {reason}")
                return "FAIL"
        elif remote:
            log(f"Artifact {art.get('path')} from a {target} worker was not uploaded; not opening remote paths.")
            return "FAIL"
        else:
            path = art.get("path")
            sha256 = art.get("sha256")
            if not isinstance(path, str) or not isinstance(sha256, str):
                log(f"Artifact missing or invalid path/sha256: {art}")
                return "FAIL"
            if not is_safe_artifact_name(path) or not local_verify(path, sha256):
                return "FAIL"
    return "PASS"

def run_loop():
    if not API_KEY:
        raise SystemExit("COURIER_VERIFIER_API_KEY is required")
    log(f"Starting Courier Verifier ({VERIFIER_ID}) pointing to {API_URL}")
    while True:
        try:
            res = requests.get(f"{API_URL}/tasks/pending_verification", headers=HEADERS, timeout=10)
            if res.status_code == 200:
                tasks = res.json().get("tasks", [])
                for task in tasks:
                    task_id = task.get("task_id")
                    result = task.get("result", {})
                    result_id = result.get("result_id") if isinstance(result, dict) else None
                    artifacts = result.get("artifacts", []) if isinstance(result, dict) else []
                    
                    log(f"Verifying task {task_id} (result {result_id})...")
                    try:
                        if not isinstance(result, dict) or result.get("status") != "SUCCESS":
                            status = result.get("status") if isinstance(result, dict) else "INVALID"
                            log(f"Task result status is {status}; rejecting verification")
                            verdict = "FAIL"
                        elif "revenue_safety_audit" in task.get("capabilities", []):
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
                                except subprocess.TimeoutExpired:
                                    log("Revenue verification timed out after 60s")
                                    verdict = "FAIL"
                                except subprocess.CalledProcessError as e:
                                    log(f"Revenue verification failed: {e.output.decode('utf-8', errors='ignore')}")
                                    verdict = "FAIL"
                        else:
                            verdict = verify_artifacts(task, result)
                    except Exception as e:
                        log(f"Unexpected error verifying task {task_id}: {e}")
                        verdict = "FAIL"
                            
                    verify_payload = {
                        "task_id": task_id,
                        "verifier_id": VERIFIER_ID,
                        "result_id": result_id,
                        "verdict": verdict,
                        "artifacts": artifacts if isinstance(artifacts, list) else []
                    }
                    try:
                        vr = requests.post(f"{API_URL}/tasks/verify", json=verify_payload, headers=HEADERS, timeout=10)
                        if vr.status_code == 200:
                            log(f"Successfully verified {task_id} with verdict {verdict}")
                        else:
                            log(f"Failed to submit verification for {task_id}: HTTP {vr.status_code} {vr.text}")
                    except Exception as e:
                        log(f"Error submitting verification for {task_id}: {e}")
        except Exception as e:
            log(f"Error polling for tasks: {e}")
            
        time.sleep(5)

if __name__ == "__main__":
    run_loop()
