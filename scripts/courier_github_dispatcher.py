#!/usr/bin/env python3
import os
import time
import requests
import json
import re
import subprocess
from pathlib import Path

API_URL = os.environ.get("COURIER_SERVER", "http://127.0.0.1:8080").rstrip("/")
API_KEY = os.environ.get("COURIER_API_KEY")
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
WORKER_ID = "GITHUB-DISPATCHER"
# Durable (not /tmp): packets must survive a dispatcher crash or host reboot.
DISPATCH_DIR = Path(os.environ.get("COURIER_GITHUB_DISPATCH_DIR", "events/github-dispatch"))
IDENTITY_FIELDS = ("goal_id", "task_id", "attempt_id", "dispatch_id", "worker_id")
SAFE_DISPATCH_ID = re.compile(r"^dispatch-[A-Za-z0-9_-]+$")

def log(msg):
    print(f"[GitHub Dispatcher] {msg}", flush=True)

def persist_packet(task):
    """Atomically write the TaskPacket; return its path, or None if it is not bindable."""
    missing = [f for f in IDENTITY_FIELDS if not isinstance(task.get(f), str) or not task[f]]
    if missing:
        log(f"Refusing task without identity fields: {', '.join(missing)}")
        return None
    if not SAFE_DISPATCH_ID.match(task["dispatch_id"]):
        log("Refusing task with unsafe dispatch_id")
        return None
    DISPATCH_DIR.mkdir(parents=True, exist_ok=True)
    path = DISPATCH_DIR / f"{task['dispatch_id']}.json"
    if path.exists():
        return None  # already persisted; resume_pending() owns it
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(task, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    return path

RESUME_EVERY_N_POLLS = 12  # supervision tick (~60s at the 5s poll below)
MAX_RESUMES_PER_DISPATCH = 3  # per process lifetime; then loud log, operator owns it
_spawned = {}  # packet file name -> Popen handle (same-process supervision)
_resume_counts = {}  # packet file name -> respawn count (retry bound)

def spawn_adapter(path):
    python_bin = "venv/bin/python3" if os.path.exists("venv/bin/python3") else "python3"
    proc = subprocess.Popen([python_bin, "scripts/github_worker_adapter.py", str(path)])
    _spawned[Path(path).name] = proc
    return proc

def _handle_alive(name):
    """True if this process spawned the packet's adapter and it still runs."""
    proc = _spawned.get(name)
    if proc is None:
        return False
    if proc.poll() is None:
        return True
    _spawned.pop(name, None)  # reaped; fall through to pid-file check
    return False

def _pid_alive(pid):
    """True if an adapter with this pid may still run. Conservative True on
    unknown errors: a missed respawn is recoverable, a double-spawn may
    double-execute and double-POST."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    return True

def handle_claimed_task(task):
    """Persist identity first; only then start execution."""
    path = persist_packet(task)
    if path is None:
        return False
    spawn_adapter(path)
    return True

def resume_pending():
    """Restart adapters for persisted dispatches that were never POSTED.

    Never double-spawns: a packet whose adapter is alive in this process
    (Popen handle) or in a surviving process (pid in state file) is
    skipped. Respawns are bounded per dispatch per process lifetime so a
    permanently failing adapter cannot hot-loop; exhaustion is logged
    loudly for the operator. Torn state counts as respawnable: the
    adapter fails fast on it, the bound stops the loop.
    """
    resumed = 0
    if not DISPATCH_DIR.is_dir():
        return 0
    for path in sorted(DISPATCH_DIR.glob("dispatch-*.json")):
        if path.name.endswith(".github-worker-state.json"):
            continue
        if _handle_alive(path.name):
            continue
        state_file = path.with_name(f"{path.stem}.github-worker-state.json")
        try:
            state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.is_file() else {}
        except (OSError, ValueError):
            state = {}
        if not isinstance(state, dict):
            state = {}
        if state.get("status") == "POSTED":
            continue
        if _pid_alive(state.get("pid")):
            continue
        if _resume_counts.get(path.name, 0) >= MAX_RESUMES_PER_DISPATCH:
            log(f"Not respawning {path.name}: respawn budget exhausted, needs operator")
            continue
        _resume_counts[path.name] = _resume_counts.get(path.name, 0) + 1
        spawn_adapter(path)
        resumed += 1
    return resumed

def run_loop():
    if not API_KEY:
        raise SystemExit("COURIER_API_KEY is required")
    log(f"Starting GitHub Dispatcher ({WORKER_ID}) pointing to {API_URL}")
    resumed = resume_pending()
    if resumed:
        log(f"Resumed {resumed} persisted dispatch(es).")
    
    # Register
    try:
        requests.post(f"{API_URL}/workers/register", json={"worker_id": WORKER_ID, "platform": "linux", "capabilities": ["github"]}, headers=HEADERS, timeout=10)
    except Exception as e:
        log(f"Failed to register: {e}")

    poll = 0
    while True:
        # Supervision tick: pick up packets whose adapter died without
        # POSTED (crash after claim, kill, host reboot of this process).
        # resume_pending is duplicate-safe (handle + pid liveness) and
        # respawn-bounded, so running it periodically cannot double-execute.
        if poll % RESUME_EVERY_N_POLLS == 0:
            try:
                revived = resume_pending()
                if revived:
                    log(f"Supervision respawned {revived} adapter(s).")
            except Exception as e:
                log(f"Supervision tick failed: {e}")
        poll += 1
        try:
            # Heartbeat
            requests.post(f"{API_URL}/workers/heartbeat", json={"worker_id": WORKER_ID}, headers=HEADERS, timeout=10)
            
            # Claim
            res = requests.post(f"{API_URL}/tasks/claim", json={"worker_id": WORKER_ID}, headers=HEADERS, timeout=10)
            if res.status_code == 200:
                task = res.json().get("task")
                if task:
                    task_id = task.get("task_id")
                    log(f"Claimed task {task_id} for GitHub.")
                    handle_claimed_task(task)
        except Exception as e:
            log(f"Error polling for tasks: {e}")
            
        time.sleep(5)

if __name__ == "__main__":
    run_loop()
