#!/usr/bin/env python3
import sys
import os
import time
import requests
import json
import re
import subprocess
from pathlib import Path

import signal

ACTIVE_ADAPTERS = {}
MAX_CONCURRENT_DISPATCHES = int(os.environ.get("COURIER_GITHUB_MAX_CONCURRENT", "5"))

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

def cleanup_active_adapters(signum=None, frame=None):
    log("Terminating active adapters...")
    for pid, (process, path) in list(ACTIVE_ADAPTERS.items()):
        try:
            process.terminate()
            process.wait(timeout=2)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass
    if signum is not None:
        sys.exit(0)

try:
    signal.signal(signal.SIGTERM, cleanup_active_adapters)
    signal.signal(signal.SIGINT, cleanup_active_adapters)
except (ValueError, AttributeError):
    pass

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

def spawn_adapter(path):
    python_bin = sys.executable
    adapter_script = Path(__file__).parent / "github_worker_adapter.py"
    process = subprocess.Popen([python_bin, str(adapter_script), str(path)])
    ACTIVE_ADAPTERS[process.pid] = (process, path)

def handle_claimed_task(task):
    """Persist identity first; only then start execution."""
    path = persist_packet(task)
    if path is None:
        return False
    spawn_adapter(path)
    return True

def resume_pending():
    """Restart adapters for persisted dispatches that were never POSTED."""
    resumed = 0
    if not DISPATCH_DIR.is_dir():
        return 0
    for path in sorted(DISPATCH_DIR.glob("dispatch-*.json")):
        if path.name.endswith(".github-worker-state.json"):
            continue
        state_file = path.with_name(f"{path.stem}.github-worker-state.json")
        if state_file.is_file():
            try:
                if json.loads(state_file.read_text(encoding="utf-8")).get("status") == "POSTED":
                    continue
            except (OSError, ValueError):
                pass
        spawn_adapter(path)
        resumed += 1
    return resumed

def check_adapters():
    """Poll running adapters, reap completed ones, and fail-closed any unposted crashes."""
    finished = []
    for pid, (process, path) in list(ACTIVE_ADAPTERS.items()):
        if process.poll() is not None:
            finished.append(pid)
            state_file = path.with_name(f"{path.stem}.github-worker-state.json")
            posted = False
            if state_file.is_file():
                try:
                    if json.loads(state_file.read_text(encoding="utf-8")).get("status") == "POSTED":
                        posted = True
                except Exception:
                    pass
            if not posted:
                log(f"Adapter for {path} exited unexpectedly with code {process.returncode} without posting result.")
                try:
                    task_data = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    task_data = {}
                fail_result = {
                    "goal_id": task_data.get("goal_id"),
                    "task_id": task_data.get("task_id"),
                    "attempt_id": task_data.get("attempt_id"),
                    "dispatch_id": task_data.get("dispatch_id"),
                    "worker_id": WORKER_ID,
                    "run_id": "adapter_crashed",
                    "result_id": f"result-{task_data.get('dispatch_id')}-failed",
                    "status": "FAILED",
                    "artifacts": [],
                    "provider": "github_dispatcher_failure",
                    "raw_result": {"reason": f"Adapter exited with code {process.returncode} without posting result"}
                }
                try:
                    requests.post(f"{API_URL}/tasks/result", json=fail_result, headers=HEADERS, timeout=10)
                except Exception as e:
                    log(f"Failed to post failure result for {path}: {e}")

                try:
                    target_state = path.with_name(f"{path.stem}.github-worker-state.json")
                    import tempfile
                    fd, tmp_file = tempfile.mkstemp(dir=str(target_state.parent) or '.', prefix=".state-tmp-")
                    with os.fdopen(fd, 'w', encoding='utf-8') as f:
                        f.write(json.dumps({"dispatch_id": task_data.get("dispatch_id"), "status": "POSTED", "error": f"exit_{process.returncode}"}, sort_keys=True) + "\n")
                    os.replace(tmp_file, target_state)
                except Exception as e:
                    log(f"Failed to write failure state for {path}: {e}")
    for pid in finished:
        ACTIVE_ADAPTERS.pop(pid, None)

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

    while True:
        try:
            check_adapters()

            # Heartbeat
            requests.post(f"{API_URL}/workers/heartbeat", json={"worker_id": WORKER_ID}, headers=HEADERS, timeout=10)
            
            # Claim (respect bounded concurrency limit)
            if len(ACTIVE_ADAPTERS) < MAX_CONCURRENT_DISPATCHES:
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
