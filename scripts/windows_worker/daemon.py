import json, time, os, sys, shutil, subprocess, hashlib, uuid
from pathlib import Path, PurePosixPath, PureWindowsPath
import urllib.request
import urllib.error
import tempfile

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
from integration_contract import canonical_result_id

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


class CanonicalLeaseLost(RuntimeError):
    """The process must stop. A stale or missing writer lease is not a retry."""

def get_app_data_dir():
    pd = os.environ.get("LOCALAPPDATA")
    # Never inside the source tree: off Windows use COURIER_HOME or ~/.courier.
    fallback = Path(os.environ.get("COURIER_HOME") or Path.home() / ".courier")
    base = (Path(pd) if pd else fallback) / "Courier"
    base.mkdir(parents=True, exist_ok=True)
    return base

APP_DATA_DIR = get_app_data_dir()
STATE_DIR = APP_DATA_DIR / "state"
LOG_DIR = APP_DATA_DIR / "logs"
STATE_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)


def read_controller_token():
    """The installer writes the key here. It does not belong in config.json."""
    path = APP_DATA_DIR / "run" / "controller.token"
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def apply_config_credentials(config):
    """Environment wins, then the controller token, then a legacy config key."""
    global API_URL, API_KEY
    if not os.environ.get("COURIER_API_KEY", "").strip():
        token = read_controller_token()
        API_KEY = token or str(config.get("COURIER_API_KEY") or "").strip()
    if not (os.environ.get("COURIER_SERVER") or os.environ.get("COURIER_SERVER_URL")):
        server = str(config.get("COURIER_SERVER") or "").strip()
        if server and server.lower() != "local":
            API_URL = server.rstrip("/")
    HEADERS["Authorization"] = f"Bearer {API_KEY}"


def require_api_key():
    """Fail closed before any network call when no API key is configured."""
    if not API_KEY:
        raise MissingCredentialError("COURIER_API_KEY is not set (environment, controller.token, or config.json); refusing to contact the Courier server.")


def setup_logging():
    import logging
    from logging.handlers import RotatingFileHandler
    log_file = LOG_DIR / "daemon.log"
    logging.basicConfig(
        handlers=[RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3)],
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    class StreamToLogger:
        def __init__(self, logger, level):
            self.logger = logger
            self.level = level
        def write(self, buf):
            for line in buf.rstrip().splitlines():
                if line.rstrip(): self.logger.log(self.level, line.rstrip())
        def flush(self): pass
    sys.stdout = StreamToLogger(logging.getLogger('STDOUT'), logging.INFO)
    sys.stderr = StreamToLogger(logging.getLogger('STDERR'), logging.ERROR)

setup_logging()

def load_config():
    config_path = APP_DATA_DIR / "config.json"
    if not config_path.exists():
        config_path = Path(__file__).parent / "config.json"
    with open(config_path, "r") as f:
        return json.load(f)
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
    payload = {
        "goal_id": task.get("goal_id"),
        "task_id": task["task_id"],
        "attempt_id": task.get("attempt_id"),
        "dispatch_id": task.get("dispatch_id"),
        "worker_id": config["WORKER_ID"],
        "run_id": result["run_id"],
        "status": status,
        "artifacts": artifacts,
        "provider": "windows_native",
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
    }
    payload["result_id"] = canonical_result_id(payload)
    return payload

def kill_process_tree(pid):
    """Best-effort: stop the child and anything PowerShell spawned under it.

    communicate(timeout=...) never kills the child on TimeoutExpired (Python
    docs), so a hung/long instruction otherwise keeps running and mutating
    the workspace after run_task() already returned FAILED. taskkill /T
    reaches the process tree on Windows; elsewhere only the direct child can
    be stopped, so its own children (if any) may still need a tree kill.
    """
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
    else:
        os.kill(pid, 9)  # non-Windows test/dev path; no tree kill available here.

def run_task(task, config):
    print(f"[{config['WORKER_ID']}] Running task {task['task_id']}...")

    # Enforce P0 CostGate before native PowerShell execution
    from scripts.resource_policy import CostGate
    if task.get("cost_class") == "unknown" or task.get("unknown_cost") is True:
        return {
            "status": "FAILED",
            "stdout": "",
            "stderr": "COST_GATE_DENIED: UNKNOWN_COST - Unknown cost class is blocked by policy firewall.",
            "goal_id": task.get("goal_id"),
            "task_id": task["task_id"],
            "worker_id": config["WORKER_ID"],
            "provider": "windows_native",
            "run_id": "blocked-by-costgate",
            "blocked": True,
        }

    # Free / included quota defaults to 0.0 EUR
    cost_class = task.get("cost_class")
    if not cost_class and isinstance(task.get("routing_decision"), dict):
        cost_class = task["routing_decision"].get("COST_CLASS")

    cost_val = task.get("estimated_cost_eur")
    if cost_val is None and cost_class in ("included_quota", "free", "local"):
        cost_val = 0.0

    cost_res = CostGate.evaluate_spend_request(
        "windows_native",
        estimated_cost_eur=cost_val,
        requested_action=task.get("requested_action", "EXECUTE_TASK"),
    )
    if not cost_res.get("allowed"):
        return {
            "status": "FAILED",
            "stdout": "",
            "stderr": f"COST_GATE_DENIED: {cost_res.get('reason')} - {cost_res.get('message', 'Blocked by CostGate')}",
            "goal_id": task.get("goal_id"),
            "task_id": task["task_id"],
            "worker_id": config["WORKER_ID"],
            "provider": "windows_native",
            "run_id": "blocked-by-costgate",
            "blocked": True,
        }

    instruction = task.get("instruction", "")

    out_clean = ""
    stderr = ""
    run_id = "win-native"


    print(f"[{config['WORKER_ID']}] Executing native PowerShell instruction.")
    import base64
    utf8_instruction = f"[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;\n{instruction}"
    encoded_instruction = base64.b64encode(utf8_instruction.encode("utf-16le")).decode("utf-8")
    cmd = ["powershell", "-EncodedCommand", encoded_instruction]
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        run_id = str(process.pid)
        try:
            stdout, stderr_out = process.communicate(timeout=600)
            out_clean = stdout.strip()
            stderr = stderr_out
            status = "SUCCESS" if process.returncode == 0 else "FAILED"
        except subprocess.TimeoutExpired:
            try:
                kill_process_tree(process.pid)
            except (OSError, subprocess.SubprocessError):
                pass
            try:
                stdout, stderr_out = process.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                stdout, stderr_out = "", ""
            out_clean = (stdout or "").strip()
            status = "FAILED"
            stderr = (stderr_out or "") + "\nTimed out after 600s; process killed, not left running."
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

_last_sys_times = None


def read_cpu_load_percent():
    """CPU load on Windows. None means the probe failed. A host without the Windows API returns 0.0."""
    global _last_sys_times
    try:
        import ctypes
        windll = ctypes.windll
    except AttributeError:
        return 0.0
    try:
        class FILETIME(ctypes.Structure):
            _fields_ = [("dwLowDateTime", ctypes.c_uint), ("dwHighDateTime", ctypes.c_uint)]
        idle = FILETIME()
        kernel = FILETIME()
        user = FILETIME()
        windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user))

        i = (idle.dwHighDateTime << 32) | idle.dwLowDateTime
        k = (kernel.dwHighDateTime << 32) | kernel.dwLowDateTime
        u = (user.dwHighDateTime << 32) | user.dwLowDateTime
        t = k + u

        if _last_sys_times is None:
            _last_sys_times = (i, t)
            return 0.0

        i_prev, t_prev = _last_sys_times
        _last_sys_times = (i, t)

        dt = t - t_prev
        di = i - i_prev
        if dt <= 0:
            return None
        return (dt - di) / dt * 100.0
    except Exception:
        return None


def is_resource_pressure_high():
    """True pauses claims. None means the probe failed and claims must pause too."""
    load = read_cpu_load_percent()
    if load is None:
        return None
    return load > 85.0

_lock_fd = None
_worker_lease = None
_lease_store = None


def get_authority_store():
    """Open the canonical lease database. A failure is raised, never cached as optional."""
    global _lease_store
    if _lease_store is None:
        from courier_runtime.lease import LeaseStore
        auth_db = STATE_DIR / "authority.db"
        _lease_store = LeaseStore(str(auth_db))
    return _lease_store


def _holder_process_is_gone(holder):
    """True only when the lease names a local process that is not still that process."""
    from courier_runtime.lease import parse_session_holder
    parsed = parse_session_holder(holder)
    if not parsed:
        return False
    import psutil
    try:
        proc = psutil.Process(parsed["pid"])
    except psutil.NoSuchProcess:
        return True
    if not proc.is_running():
        return True
    return abs(proc.create_time() - parsed["create_time"]) > 0.05


def acquire_lock(worker_id):
    """Return the lock path, or None when another worker already holds it.

    A missing temp directory or a failed write is raised. Those are not a
    second instance, and they must not look like a clean exit.
    """
    global _lock_fd, _worker_lease
    if _lock_fd is not None:
        return None
    import psutil
    lock_file = Path(tempfile.gettempdir()) / f"courier_worker_{worker_id}.lock"
    fd = os.open(str(lock_file), os.O_CREAT | os.O_RDWR)
    try:
        if os.name == "nt" or "msvcrt" in sys.modules:
            import msvcrt
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except ImportError:
        os.close(fd)
        raise
    except OSError:
        os.close(fd)
        return None
    try:
        os.ftruncate(fd, 0)
        lock_data = json.dumps({'pid': os.getpid(), 'process_create_time': psutil.Process(os.getpid()).create_time()})
        os.write(fd, lock_data.encode('utf-8'))
    except OSError:
        os.close(fd)
        raise

    _lock_fd = fd

    # The file lock is not a canonical lease. Without a live LeaseStore grant
    # the worker must not start, and the file lock must not stay behind.
    scope = f"worker:{worker_id}"
    try:
        store = get_authority_store()
        from courier_runtime.lease import LeaseConflict, format_session_holder
        holder = format_session_holder(worker_id, os.getpid(), psutil.Process(os.getpid()).create_time(), str(uuid.uuid4()))
        try:
            _worker_lease = store.acquire(scope, holder, "daemon_loop", ttl_s=3600)
        except LeaseConflict:
            current = store.current(scope)
            if current is not None and not _holder_process_is_gone(current.holder):
                raise
            if current is not None:
                store.release(current)
            _worker_lease = store.acquire(scope, holder, "daemon_loop", ttl_s=3600)
    except Exception as exc:
        release_lock(lock_file)
        raise RuntimeError(f"Courier cannot start without a canonical writer lease: {exc}") from exc

    return lock_file


def _require_canonical_lease():
    """Refuse work when the start lease is missing or its fencing token moved."""
    if _worker_lease is None:
        raise CanonicalLeaseLost("Courier cannot run without a canonical writer lease")
    store = get_authority_store()
    try:
        store.check_write(_worker_lease.scope, _worker_lease.token)
    except Exception as exc:
        raise CanonicalLeaseLost(
            f"Courier cannot run without a canonical writer lease: {exc}"
        ) from exc


def release_lock(lock_path=None):
    global _lock_fd, _worker_lease
    if _worker_lease is not None:
        store = get_authority_store()
        if store is not None:
            try:
                store.release(_worker_lease)
            except Exception:
                pass
        _worker_lease = None
    if _lock_fd is not None:
        try:
            if os.name == "nt":
                import msvcrt
                os.lseek(_lock_fd, 0, os.SEEK_SET)
                msvcrt.locking(_lock_fd, msvcrt.LK_UNLCK, 1)
            else:
                try:
                    import fcntl
                    fcntl.flock(_lock_fd, fcntl.LOCK_UN)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            os.close(_lock_fd)
        except OSError:
            pass
        _lock_fd = None
    if lock_path and os.path.exists(lock_path):
        try:
            os.remove(lock_path)
        except OSError:
            pass



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
                
                # 2. Resource Pressure Check. A failed probe is not "idle".
                pressure = is_resource_pressure_high()
                if pressure is None:
                    print(f"[{worker_id}] Resource check failed. Pausing claims.")
                    time.sleep(60)
                    continue
                if pressure:
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
                    _require_canonical_lease()
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
                    
            except CanonicalLeaseLost:
                raise
            except Exception as e:
                print(f"[{worker_id}] Loop error: {e}. Backing off {backoff}s.")
                time.sleep(backoff)
                backoff = min(max_backoff, backoff * 2)
                continue
                
            time.sleep(10)
            
    finally:
        release_lock(lock_path)

if __name__ == "__main__":
    try:
        loop()
    except MissingCredentialError as e:
        print(f"FATAL: {e}", file=sys.stderr)
        sys.exit(2)
    except CanonicalLeaseLost as e:
        print(f"FATAL: {e}", file=sys.stderr)
        sys.exit(3)
