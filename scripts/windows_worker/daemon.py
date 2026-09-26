import json, time, os, sys, shutil, subprocess, uuid, hashlib
from pathlib import Path, PurePosixPath, PureWindowsPath
import urllib.request
import urllib.error
import tempfile

# No fallback key exists. The key comes from COURIER_API_KEY or, failing that,
# from config.json where bootstrap.ps1 stores it; the server URL from
# COURIER_SERVER (COURIER_SERVER_URL accepted), then config.json, then the default.
DEFAULT_SERVER = "http://192.168.178.162:8080"
API_URL = (os.environ.get("COURIER_SERVER") or os.environ.get("COURIER_SERVER_URL") or DEFAULT_SERVER).rstrip("/")
API_KEY = os.environ.get("COURIER_API_KEY", "").strip()
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

class MissingCredentialError(RuntimeError):
    pass

def apply_config_credentials(config):
    """Environment wins; otherwise use the values bootstrap.ps1 wrote to config.json."""
    global API_URL, API_KEY
    if not os.environ.get("COURIER_API_KEY", "").strip():
        API_KEY = str(config.get("COURIER_API_KEY") or "").strip()
    if not (os.environ.get("COURIER_SERVER") or os.environ.get("COURIER_SERVER_URL")):
        server = str(config.get("COURIER_SERVER") or "").strip()
        if server and server.lower() != "local":
            API_URL = server.rstrip("/")
    HEADERS["Authorization"] = f"Bearer {API_KEY}"

def require_api_key():
    """Fail closed before any network call when no API key is configured."""
    if not API_KEY:
        raise MissingCredentialError("COURIER_API_KEY is not set (environment or config.json); refusing to contact the Courier server.")

def load_config():
    config_path = Path(__file__).parent / "config.json"
    with open(config_path, "r") as f:
        return json.load(f)

STATE_DIR = Path(__file__).parent / "state"
MAX_RESULT_POST_ATTEMPTS = 5

# Only capabilities run_task() can actually execute (native PowerShell). config.json
# WORKER_CAPABILITIES is not authoritative: e.g. "antigravity" would route agy tasks here.
CAPABILITIES = ["windows"]

def register_worker(worker_id, release_task=False):
    require_api_key()
    req = urllib.request.Request(f"{API_URL}/workers/register", method="POST")
    for k, v in HEADERS.items(): req.add_header(k, v)
    payload = {"worker_id": worker_id, "platform": "windows", "capabilities": list(CAPABILITIES)}
    if release_task:
        # Tells the server this worker no longer holds its task; the server's
        # restart recovery then quarantines it (HUMAN_REQUIRED) instead of replaying.
        payload["current_task"] = None
    data = json.dumps(payload).encode("utf-8")
    try:
        urllib.request.urlopen(req, data=data, timeout=10)
        return True
    except Exception as e:
        print(f"[{worker_id}] Failed to register: {e}")
        return False

def upload_enabled(config):
    """Artifact upload needs the server artifact store (P3 cutover); opt-in until then."""
    flag = os.environ.get("COURIER_ARTIFACT_UPLOAD", str(config.get("ARTIFACT_UPLOAD", "")))
    return str(flag).strip().lower() in ("1", "true", "yes")

def upload_artifact(task, art):
    """Upload one artifact's bytes; returns (OK|REJECTED|UNDELIVERED, record)."""
    require_api_key()
    name = art["path"]
    if not is_safe_artifact_path(name) or not Path(name).is_file():
        return "REJECTED", None
    data = Path(name).read_bytes()
    if hashlib.sha256(data).hexdigest() != art["sha256"]:
        print(f"[Windows Worker] Artifact {name} changed after hashing; not uploading.")
        return "REJECTED", None
    meta = {"name": name, "sha256": art["sha256"], "size": len(data),
            **{f: task.get(f) for f in ("goal_id", "task_id", "attempt_id", "dispatch_id", "worker_id")}}
    req = urllib.request.Request(f"{API_URL}/artifacts", method="POST")
    for k, v in HEADERS.items():
        req.add_header(k, v)
    req.add_header("Content-Type", "application/octet-stream")
    req.add_header("X-Courier-Artifact", json.dumps(meta, separators=(",", ":")))
    try:
        with urllib.request.urlopen(req, data=data, timeout=30) as resp:
            record = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"[Windows Worker] Artifact upload failed: HTTP {e.code}")
        return ("REJECTED" if e.code < 500 else "UNDELIVERED"), None
    except Exception as e:
        print(f"[Windows Worker] Artifact upload failed: {e}")
        return "UNDELIVERED", None
    if record.get("sha256") != art["sha256"] or record.get("size") != len(data) or not str(record.get("artifact_id", "")).startswith("art-"):
        return "REJECTED", None
    return "OK", record

def upload_pending_artifacts(task, state_file):
    """Attach server artifact_ids to the stored result; READY when all are uploaded."""
    for art in task["result_payload"].get("artifacts", []):
        if "artifact_id" in art:
            continue
        outcome, record = upload_artifact(task, art)
        if outcome != "OK":
            return outcome
        art["artifact_id"], art["size"] = record["artifact_id"], record["size"]
        persist_task(state_file, task)
    return "READY"

def http_post_result(res):
    """Deliver a stored result; returns DELIVERED, REJECTED or UNDELIVERED.

    Only transport errors and 5xx are retried; a 4xx is the server's final
    answer for this exact payload (200 IGNORED means already processed).
    """
    require_api_key()
    data = json.dumps(res).encode("utf-8")
    for attempt in range(MAX_RESULT_POST_ATTEMPTS):
        req = urllib.request.Request(f"{API_URL}/tasks/result", method="POST")
        for k, v in HEADERS.items(): req.add_header(k, v)
        try:
            urllib.request.urlopen(req, data=data, timeout=10)
            return "DELIVERED"
        except urllib.error.HTTPError as e:
            if e.code < 500:
                print(f"[Windows Worker] Result rejected permanently: HTTP {e.code} {e.read().decode('utf-8', 'replace')}")
                return "REJECTED"
            print(f"[Windows Worker] Failed to post result: HTTP {e.code}")
        except Exception as e:
            print(f"[Windows Worker] Failed to post result: {e}")
        time.sleep(2 ** attempt)
    return "UNDELIVERED"

# current_task.json records how far a claimed task got (at-most-once execution):
#   CLAIMED      -> execution has not begun; safe to run
#   STARTED      -> execution may have had effects; never re-run after a crash
#   RESULT_READY -> result_payload is final; only (re)deliver it, never recompute
#   RELEASE_PENDING -> result was rejected (4xx); release the task to the server
def persist_task(path, task):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    with open(tmp_path, "w") as f:
        json.dump(task, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)

def is_safe_artifact_path(name):
    """Artifacts are workspace-relative (the daemon's cwd, which PowerShell
    inherits). Reject absolute, drive-qualified, UNC and '..' paths under both
    Windows and POSIX rules, matching the integration contract."""
    if not isinstance(name, str) or not name:
        return False
    for pure in (PureWindowsPath(name), PurePosixPath(name)):
        if pure.is_absolute() or pure.drive or pure.root or ".." in pure.parts:
            return False
    return True

def build_result_payload(task, result, config):
    """Bind the execution outcome to the server-issued dispatch identity."""
    status = result["status"]
    artifacts = []
    if status == "SUCCESS":
        for expected in task.get("artifacts", []):
            name = expected.get("path") if isinstance(expected, dict) else expected
            if not is_safe_artifact_path(name):
                status = "FAILED"
                result["stderr"] = result.get("stderr", "") + f"\nUnsafe artifact path: {name}"
                artifacts = []
                break
            path = Path(name)
            if not path.is_file():
                status = "FAILED"
                result["stderr"] = result.get("stderr", "") + f"\nMissing artifact: {path}"
                artifacts = []
                break
            artifacts.append({"path": str(expected.get("path") if isinstance(expected, dict) else expected),
                              "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        if status == "SUCCESS" and not artifacts:
            status = "FAILED"
            result["stderr"] = result.get("stderr", "") + "\nNo artifact evidence for success"
    return {
        "goal_id": task.get("goal_id"),
        "task_id": task["task_id"],
        "attempt_id": task.get("attempt_id"),
        "dispatch_id": task.get("dispatch_id"),
        "worker_id": config["WORKER_ID"],
        "run_id": result["run_id"],
        "result_id": f"result-{uuid.uuid4().hex}",
        "status": status,
        "artifacts": artifacts,
        "provider": "windows_native",
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
    }

def run_task(task, config):
    print(f"[{config['WORKER_ID']}] Running task {task['task_id']}...")
    
    instruction = task.get("instruction", "")
    
    out_clean = ""
    stderr = ""
    run_id = "win-native"
    
    print(f"[{config['WORKER_ID']}] Executing native PowerShell instruction.")
    import base64
    encoded_instruction = base64.b64encode(instruction.encode("utf-16le")).decode("utf-8")
    cmd = ["powershell", "-EncodedCommand", encoded_instruction]
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        run_id = str(process.pid)
        stdout, stderr_out = process.communicate(timeout=600)
        out_clean = stdout.strip()
        stderr = stderr_out
        status = "SUCCESS" if process.returncode == 0 else "FAILED"
    except Exception as e:
        status = "FAILED"
        stderr = str(e)
            
    res_json = {
        "status": status,
        "stdout": out_clean,
        "stderr": stderr
    }
        
    res_json["goal_id"] = task.get("goal_id")
    res_json["task_id"] = task["task_id"]
    res_json["worker_id"] = config["WORKER_ID"]
    res_json["provider"] = "windows_native"
    res_json["run_id"] = run_id
    
    return res_json

def is_resource_pressure_high():
    try:
        # Check CPU load
        out = subprocess.check_output(["powershell", "-NoProfile", "-Command", "(Get-WmiObject Win32_Processor).LoadPercentage"], text=True, timeout=5)
        loads = [int(x.strip()) for x in out.split() if x.strip().isdigit()]
        if loads and sum(loads)/len(loads) > 85:
            return True
        return False
    except Exception:
        # Defaults to safe (no pressure) if check fails to prevent starvation, but we could also back off
        return False

def acquire_lock(worker_id):
    lock_file = Path(tempfile.gettempdir()) / f"courier_worker_{worker_id}.lock"
    try:
        # Try to open file in exclusive creation mode.
        fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_RDWR)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return lock_file
    except FileExistsError:
        # Check if the process is actually running
        try:
            with open(lock_file, "r") as f:
                pid = int(f.read().strip())
            # In Windows, we can check if PID exists using tasklist
            out = subprocess.check_output(["tasklist", "/FI", f"PID eq {pid}"], text=True)
            if str(pid) not in out:
                # Stale lock
                os.remove(lock_file)
                return acquire_lock(worker_id)
        except Exception:
            pass
        return None

def loop():
    config = load_config()
    apply_config_credentials(config)
    require_api_key()
    worker_id = config["WORKER_ID"]
    
    lock_path = acquire_lock(worker_id)
    if not lock_path:
        print(f"[{worker_id}] Another instance is already running. Exiting to prevent duplicates.")
        sys.exit(0)
    
    try:
        print(f"[{worker_id}] Windows Worker HTTP Daemon started. PID={os.getpid()}")
        
        backoff = 10
        max_backoff = 300
        state_file = STATE_DIR / "current_task.json"
        task = None
        release_task = False
        if state_file.exists():
            task = json.loads(state_file.read_text())
            if task.get("worker_phase") not in ("CLAIMED", "RESULT_READY"):
                task["worker_phase"] = "STARTED"
            print(f"[{worker_id}] Found unfinished task {task['task_id']} in phase {task['worker_phase']}.")
        
        while True:
            try:
                if task and task["worker_phase"] == "STARTED":
                    # Interrupted mid-execution: effects may exist, never replay.
                    print(f"[{worker_id}] Task {task['task_id']} was interrupted during execution; releasing to Courier recovery.")
                    release_task = True
                    task = None
                if release_task:
                    if not register_worker(worker_id, release_task=True):
                        raise RuntimeError("could not release interrupted task")
                    state_file.unlink()
                    release_task = False

                # 1. Register/Heartbeat
                req = urllib.request.Request(f"{API_URL}/workers/heartbeat", method="POST")
                for k, v in HEADERS.items(): req.add_header(k, v)
                data = json.dumps({"worker_id": worker_id}).encode("utf-8")
                try:
                    urllib.request.urlopen(req, data=data, timeout=10)
                except urllib.error.HTTPError as e:
                    if e.code == 404:
                        register_worker(worker_id)
                
                # 2. Resource Pressure Check
                if is_resource_pressure_high():
                    print(f"[{worker_id}] Resource pressure high. Pausing claims.")
                    time.sleep(60)
                    continue
                
                # 3. Claim Task (only when no finished result is pending)
                if not task:
                    req = urllib.request.Request(f"{API_URL}/tasks/claim", method="POST")
                    for k, v in HEADERS.items(): req.add_header(k, v)
                    res = urllib.request.urlopen(req, data=data, timeout=10)
                    res_data = json.loads(res.read().decode("utf-8"))
                    task = res_data.get("task")
                    if task:
                        task["worker_phase"] = "CLAIMED"
                        persist_task(state_file, task)

                if task and task["worker_phase"] == "CLAIMED":
                    task["worker_phase"] = "STARTED"
                    persist_task(state_file, task)
                    result = run_task(task, config)
                    task["result_payload"] = build_result_payload(task, result, config)
                    task["worker_phase"] = "RESULT_READY"
                    persist_task(state_file, task)

                if task:
                    outcome = upload_pending_artifacts(task, state_file) if upload_enabled(config) else "READY"
                    if outcome == "READY":
                        outcome = http_post_result(task["result_payload"])
                    if outcome == "UNDELIVERED":
                        print(f"[{worker_id}] Result for {task['task_id']} not delivered yet; keeping it for redelivery.")
                    elif outcome == "REJECTED":
                        persist_task(STATE_DIR / f"rejected_result_{task['task_id']}.json", task)
                        # The server keeps the task assigned after a 4xx; release it so recovery
                        # quarantines it instead of leaving us WORKER_BUSY forever. The phase is
                        # persisted first, so a crash here still releases on restart.
                        task["worker_phase"] = "RELEASE_PENDING"
                        persist_task(state_file, task)
                        print(f"[{worker_id}] Task {task['task_id']} result REJECTED; releasing it.")
                        release_task = True
                        task = None
                    else:
                        state_file.unlink()
                        print(f"[{worker_id}] Task {task['task_id']} result {outcome}.")
                        task = None
                backoff = 10
                    
            except Exception as e:
                print(f"[{worker_id}] Loop error: {e}. Backing off {backoff}s.")
                time.sleep(backoff)
                backoff = min(max_backoff, backoff * 2)
                continue
                
            time.sleep(10)
            
    finally:
        if os.path.exists(lock_path):
            os.remove(lock_path)

if __name__ == "__main__":
    try:
        loop()
    except MissingCredentialError as e:
        print(f"FATAL: {e}", file=sys.stderr)
        sys.exit(2)
