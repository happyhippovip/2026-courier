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

# --- H-Paket (staging candidate): log size limit, backoff, self-exit watchdog ---
LOG_FILE = os.environ.get("COURIER_VERIFIER_LOG")  # if set: own rotating file, no stdout growth
LOG_MAX_BYTES = int(os.environ.get("COURIER_VERIFIER_LOG_MAX_BYTES", 5 * 1024 * 1024))
LOG_BACKUPS = int(os.environ.get("COURIER_VERIFIER_LOG_BACKUPS", 3))
BACKOFF_CAP_S = float(os.environ.get("COURIER_VERIFIER_BACKOFF_CAP_S", 300))
MAX_CONSEC_ERRORS = int(os.environ.get("COURIER_VERIFIER_MAX_CONSEC_ERRORS", 20))
EXIT_WATCHDOG = 4


def _rotate(path, max_bytes=None, backups=None):
    max_bytes = LOG_MAX_BYTES if max_bytes is None else max_bytes
    backups = LOG_BACKUPS if backups is None else backups
    try:
        if os.path.getsize(path) < max_bytes:
            return
    except OSError:
        return
    try:
        for i in range(backups - 1, 0, -1):
            src, dst = f"{path}.{i}", f"{path}.{i + 1}"
            if os.path.exists(src):
                os.replace(src, dst)
        if backups > 0:
            os.replace(path, f"{path}.1")
        else:
            open(path, "w").close()
    except OSError:
        pass  # locked/busy log (Windows): skip rotation, keep appending; never kill the verifier


def log(msg):
    line = f"[Verifier] {msg}"
    if LOG_FILE:
        _rotate(LOG_FILE)
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            print(line, flush=True)  # log file unusable: fall back to stdout
    else:
        print(line, flush=True)


def _redact(text):
    if API_KEY:
        text = str(text).replace(API_KEY, "***")
    return text


def next_delay(base, consec_errors, cap=None):
    """Exponential backoff: base * 2**(n-1), capped. n=0 -> base."""
    cap = BACKOFF_CAP_S if cap is None else cap
    if consec_errors <= 0:
        return base
    return min(cap, base * (2 ** min(consec_errors - 1, 30)))

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

def run_loop(sleep=None, max_iterations=None):
    sleep = sleep or (lambda s: time.sleep(s))  # resolve at call time (tests patch time.sleep)
    if not API_KEY:
        raise SystemExit("COURIER_VERIFIER_API_KEY is required")
    log(f"Starting Courier Verifier ({VERIFIER_ID}) pointing to {API_URL}")
    consec_errors = 0
    iterations = 0
    while max_iterations is None or iterations < max_iterations:
        iterations += 1
        try:
            res = requests.get(f"{API_URL}/tasks/pending_verification", headers=HEADERS, timeout=10)
            if not (200 <= res.status_code < 300):
                raise RuntimeError(f"poll HTTP {res.status_code}")
            if res.status_code == 200:
                tasks = res.json().get("tasks", [])
                for task in tasks:
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
                        else:
                            log(f"Failed to submit verification for {task_id}: HTTP {vr.status_code} {_redact(vr.text)}")
                    except Exception as e:
                        t_id = task.get('task_id', 'unknown') if isinstance(task, dict) else 'unknown'
                        log(f"Error processing task {t_id}: {_redact(e)}")
            consec_errors = 0
        except Exception as e:
            consec_errors += 1
            log(f"Error polling for tasks ({consec_errors}/{MAX_CONSEC_ERRORS}): {_redact(e)}")
            if MAX_CONSEC_ERRORS > 0 and consec_errors >= MAX_CONSEC_ERRORS:
                log(f"Watchdog: {consec_errors} consecutive poll errors; clean self-exit {EXIT_WATCHDOG}")
                raise SystemExit(EXIT_WATCHDOG)

        sleep(next_delay(governor.get_poll_interval(), consec_errors))

if __name__ == "__main__":
    run_loop()
