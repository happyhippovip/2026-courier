#!/usr/bin/env python3
import os
import sys
import time
import requests
import hashlib
from pathlib import Path
from resource_governor import governor

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.artifact_store import DEFAULT_MAX_BYTES, is_safe_artifact_name, verify_uploaded_artifact

API_URL = os.environ.get("COURIER_SERVER", "http://127.0.0.1:8080").rstrip("/")
API_KEY = os.environ.get("COURIER_VERIFIER_API_KEY")
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

MAX_ARTIFACT_BYTES = int(os.environ.get("COURIER_ARTIFACT_MAX_BYTES", DEFAULT_MAX_BYTES))
REMOTE_TARGETS = ("mac", "windows")
FETCH_META_TIMEOUT = int(os.environ.get("COURIER_FETCH_META_TIMEOUT", "10"))
FETCH_BLOB_TIMEOUT = int(os.environ.get("COURIER_FETCH_BLOB_TIMEOUT", "30"))
FETCH_MAX_ATTEMPTS = int(os.environ.get("COURIER_FETCH_ATTEMPTS", "3"))
FETCH_BACKOFF_SECONDS = (1, 2)


def _get_with_retry(url, timeout):
    """GET with bounded retry on transient transport errors only.

    Retries Timeout/ConnectionError with backoff. HTTP errors (including 5xx)
    and evidence failures propagate immediately to preserve fail-closed FAIL.
    """
    last = None
    for attempt in range(max(1, FETCH_MAX_ATTEMPTS)):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            resp.raise_for_status()
            return resp
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last = e
            if attempt < FETCH_MAX_ATTEMPTS - 1:
                time.sleep(FETCH_BACKOFF_SECONDS[min(attempt, len(FETCH_BACKOFF_SECONDS) - 1)])
    raise last


def fetch_artifact(artifact_id):
    """Return (record, bytes) of the server-side uploaded copy."""
    meta = _get_with_retry(f"{API_URL}/artifacts/{artifact_id}/meta", FETCH_META_TIMEOUT)
    blob = _get_with_retry(f"{API_URL}/artifacts/{artifact_id}", FETCH_BLOB_TIMEOUT)
    if len(blob.content) > MAX_ARTIFACT_BYTES:
        raise ValueError("artifact exceeds size limit")
    return meta.json(), blob.content


def verify_artifacts(task, result, fetch=fetch_artifact, local_verify=None):
    """PASS only if every artifact is independently confirmed.

    Uploaded artifacts are re-hashed from the server copy. Mac/Windows artifacts
    must be uploaded: the verifier never opens a remote worker's local path.
    """
    local_verify = local_verify or verify_artifact
    artifacts = result.get("artifacts", [])
    if not isinstance(artifacts, list) or any(not isinstance(art, dict) for art in artifacts):
        log("Malformed artifact evidence; failing closed.")
        return "FAIL"
    expected_paths = set(task.get("artifacts") or [])
    if expected_paths and not expected_paths.issubset({art.get("path") for art in artifacts}):
        log("Result is missing expected artifacts.")
        return "FAIL"
    if not artifacts:
        log("No artifact evidence.")
        return "FAIL"
    target = str(task.get("target_capability") or task.get("target_agent") or "").lower()
    remote = any(t in target for t in REMOTE_TARGETS)
    for art in artifacts:
        if "artifact_id" in art:
            try:
                record, data = fetch(art["artifact_id"])
            except Exception as e:
                log(f"Cannot fetch uploaded artifact: {e}")
                return "FAIL"
            task_expected = task.get("expected_artifacts", {}).get(art.get("path")) or task.get("expected_sha256")
            if task_expected:
                if hashlib.sha256(data).hexdigest() != task_expected:
                    log(f"Hash mismatch against expected_sha256 for {art.get('path')}")
                    return "FAIL"
            ok, reason = verify_uploaded_artifact(data, record, art, task)
            if not ok:
                log(f"Uploaded artifact rejected: {reason}")
                return "FAIL"
        elif remote:
            log(f"Artifact {art.get('path')} from a {target} worker was not uploaded; not opening remote paths.")
            return "FAIL"
        elif not is_safe_artifact_name(art.get("path")) or not local_verify(art.get("path"), art.get("sha256")):
            return "FAIL"
    return "PASS"

SUBMIT_MAX_FAILURES = 3  # consecutive per-task failures before backing off
SUBMIT_BACKOFF_POLLS = 12  # polls to skip a failing task (~60s at 5s poll)
_task_failures = {}  # task_id -> consecutive failure count
_task_skip_until = {}  # task_id -> poll index (exclusive) to resume at

def _should_skip_task(task_id, poll):
    return _task_skip_until.get(task_id, -1) > poll

def _record_task_failure(task_id, poll):
    """Count a verify-exception or verdict-submit failure; back the task off.

    Backoff is rate-limiting, not give-up: after SUBMIT_BACKOFF_POLLS the
    task is retried, so recovery (server back, artifact available) resumes
    automatically. Without this, one stuck task re-runs full verification
    (artifact downloads incl. fetch retries) every poll forever.
    """
    n = _task_failures.get(task_id, 0) + 1
    _task_failures[task_id] = n
    if n >= SUBMIT_MAX_FAILURES:
        _task_skip_until[task_id] = poll + SUBMIT_BACKOFF_POLLS
        log(f"Backing off task {task_id} for {SUBMIT_BACKOFF_POLLS} polls after {n} consecutive failures")
    return n

def _record_task_success(task_id):
    _task_failures.pop(task_id, None)
    _task_skip_until.pop(task_id, None)

def run_loop():
    if not API_KEY:
        raise SystemExit("COURIER_VERIFIER_API_KEY is required")
    log(f"Starting Courier Verifier ({VERIFIER_ID}) pointing to {API_URL}")
    poll = 0
    while True:
        try:
            res = requests.get(f"{API_URL}/tasks/pending_verification", headers=HEADERS, timeout=10)
            if res.status_code == 200:
                tasks = res.json().get("tasks", [])
                for task in tasks:
                    if _should_skip_task(task.get("task_id"), poll):
                        continue
                    try:
                        task_id = task.get("task_id")
                        result = task.get("result") or {}
                        result_id = result.get("result_id")
                        artifacts = result.get("artifacts", [])

                        log(f"Verifying task {task_id} (result {result_id})...")

                        if "revenue_safety_audit" in (task.get("capabilities") or []):
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
                                    subprocess.check_output(cmd, stderr=subprocess.STDOUT)
                                    verdict = "PASS"
                                except subprocess.CalledProcessError as e:
                                    log(f"Revenue verification failed: {e.output.decode('utf-8', errors='ignore')}")
                                    verdict = "FAIL"
                        else:
                            verdict = verify_artifacts(task, result)

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
                            _record_task_success(task_id)
                        else:
                            log(f"Failed to submit verification for {task_id}: HTTP {vr.status_code} {vr.text}")
                            _record_task_failure(task_id, poll)
                    except Exception as e:
                        t_id = task.get('task_id', 'unknown') if isinstance(task, dict) else 'unknown'
                        log(f"Error processing task {t_id}: {e}")
                        _record_task_failure(task.get("task_id"), poll)
        except Exception as e:
            log(f"Error polling for tasks: {e}")

        time.sleep(governor.get_poll_interval())
        poll += 1

if __name__ == "__main__":
    run_loop()
