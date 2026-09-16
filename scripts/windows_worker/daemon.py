import json, time, os, sys, shutil, subprocess
from pathlib import Path
import urllib.request
import urllib.error
import tempfile
import uuid
import hashlib

def load_config():
    config_path = Path(__file__).parent / "config.json"
    if config_path.exists():
        with open(config_path, "r") as f:
            return json.load(f)
    return {}

_cfg = load_config()
API_URL = os.environ.get("COURIER_SERVER") or _cfg.get("COURIER_SERVER") or "http://127.0.0.1:8080"

# API_KEY: environment variable or OS keyring ONLY — never from config.json or hardcoded defaults.
try:
    import keyring as _keyring
    API_KEY = os.environ.get("COURIER_API_KEY") or _keyring.get_password("courier_worker", "courier_api_key")
except Exception:
    API_KEY = os.environ.get("COURIER_API_KEY")

if not API_KEY and __name__ == "__main__":
    print("[Windows Worker] FATAL: No COURIER_API_KEY found in environment or OS keyring.", flush=True)
    print("[Windows Worker] Set via: $env:COURIER_API_KEY or keyring.set_password('courier_worker','courier_api_key','<key>')", flush=True)
    sys.exit(1)
HEADERS = {
    "Authorization": f"Bearer {API_KEY or ''}",
    "Content-Type": "application/json"
}

def register_worker(worker_id):
    req = urllib.request.Request(f"{API_URL}/workers/register", method="POST")
    for k, v in HEADERS.items(): req.add_header(k, v)
    cost_class = os.environ.get("WORKER_COST_CLASS", "low")
    data = json.dumps({"worker_id": worker_id, "platform": "windows", "capabilities": ["windows"], "cost_class": cost_class}).encode("utf-8")
    try:
        urllib.request.urlopen(req, data=data, timeout=10)
        return True
    except Exception as e:
        print(f"[{worker_id}] Failed to register: {e}")
        return False

def http_post_result(res):
    req = urllib.request.Request(f"{API_URL}/tasks/result", method="POST")
    for k, v in HEADERS.items(): req.add_header(k, v)
    data = json.dumps(res).encode("utf-8")
    for attempt in range(5):
        try:
            urllib.request.urlopen(req, data=data, timeout=10)
            return True
        except urllib.error.HTTPError as e:
            if e.code in [400, 404, 409]:
                print(f"[Windows Worker] Permanent server decision HTTP {e.code}: Courier server remains authority. Discarding local state.")
                return False
            print(f"[Windows Worker] Transient HTTP {e.code} posting result: {e}")
            time.sleep(2 ** attempt)
        except Exception as e:
            print(f"[Windows Worker] Failed to post result: {e}")
            time.sleep(2 ** attempt)
    return False

def kill_process_tree(pid):
    if not pid:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
        else:
            import signal
            # Kill child processes first if any
            try:
                children = subprocess.check_output(["pgrep", "-P", str(pid)], text=True, stderr=subprocess.DEVNULL).split()
                for c in children:
                    try:
                        os.kill(int(c), signal.SIGKILL)
                    except Exception:
                        pass
            except Exception:
                pass

            # If it is its own process group leader, kill process group; otherwise kill pid
            try:
                pgid = os.getpgid(pid)
                if pgid == pid:
                    os.killpg(pgid, signal.SIGKILL)
                else:
                    os.kill(pid, signal.SIGKILL)
            except Exception:
                try:
                    os.kill(pid, signal.SIGKILL)
                except Exception:
                    pass
    except Exception as e:
        print(f"Failed to kill process tree for PID {pid}: {e}", flush=True)

def run_task(task, config):
    print(f"[{config['WORKER_ID']}] Running task {task['task_id']}...", flush=True)
    
    instruction = task.get("instruction", "")
    
    out_clean = ""
    stderr = ""
    run_id = "win-native"
    
    print(f"[{config['WORKER_ID']}] Executing native PowerShell instruction.", flush=True)
    cmd = ["powershell", "-Command", instruction]
    process = None
    try:
        if sys.platform == "win32":
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=os.setsid if hasattr(os, "setsid") else None
            )
        run_id = str(process.pid)
        stdout, stderr_out = process.communicate(timeout=600)
        out_clean = stdout.strip()
        stderr = stderr_out
        status = "SUCCESS" if process.returncode == 0 else "FAILED"
    except subprocess.TimeoutExpired:
        status = "FAILED"
        stderr = "Timeout of 600s exceeded. Exact child process tree terminated."
        out_clean = ""
        if process:
            kill_process_tree(process.pid)
            try:
                process.communicate(timeout=5)
            except Exception:
                pass
    except Exception as e:
        status = "FAILED"
        stderr = str(e)
        out_clean = ""
        if process:
            kill_process_tree(process.pid)
            try:
                process.communicate(timeout=5)
            except Exception:
                pass
            
    artifacts = []
    if status == "SUCCESS":
        expected = task.get("artifacts", [])
        workspace = Path(os.getcwd())
        for relative_name in expected:
            artifact_path = workspace / relative_name
            if artifact_path.is_file():
                artifacts.append({
                    "path": relative_name,
                    "sha256": hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
                })
            else:
                status = "FAILED"
                stderr += f"\nMissing artifact: {relative_name}"

    res_json = {
        "status": status,
        "stdout": out_clean,
        "stderr": stderr,
        "goal_id": task.get("goal_id"),
        "task_id": task.get("task_id"),
        "attempt_id": task.get("attempt_id"),
        "dispatch_id": task.get("dispatch_id"),
        "worker_id": task.get("worker_id") or config["WORKER_ID"],
        "provider": "windows_native",
        "run_id": run_id,
        "result_id": f"result-{uuid.uuid4().hex}",
        "artifacts": artifacts if status == "SUCCESS" else []
    }
    
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

def is_pid_running(pid):
    try:
        pid = int(pid)
        if sys.platform == "win32":
            out = subprocess.check_output(["tasklist", "/FI", f"PID eq {pid}"], text=True, stderr=subprocess.DEVNULL)
            return str(pid) in out
        else:
            os.kill(pid, 0)
            return True
    except (OSError, ValueError, subprocess.SubprocessError):
        return False

def acquire_lock(worker_id):
    lock_file = Path(tempfile.gettempdir()) / f"courier_worker_{worker_id}.lock"
    pid_file = Path(__file__).parent / "daemon.pid"
    
    if lock_file.exists():
        try:
            old_pid = int(lock_file.read_text().strip())
            if is_pid_running(old_pid):
                return None
            else:
                try:
                    lock_file.unlink()
                except OSError:
                    pass
        except Exception:
            pass

    try:
        fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_RDWR)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        try:
            pid_file.write_text(str(os.getpid()))
        except Exception:
            pass
        return lock_file
    except FileExistsError:
        return None

def loop():
    config = load_config()
    worker_id = os.environ.get("COURIER_WORKER_ID") or config.get("WORKER_ID", "default-win-worker")
    
    if not API_KEY:
        print("[Windows Worker] FATAL: No COURIER_API_KEY found in environment or OS keyring.", flush=True)
        print("[Windows Worker] Set via: $env:COURIER_API_KEY or keyring.set_password('courier_worker','courier_api_key','<key>')", flush=True)
        sys.exit(1)
        
    lock_path = acquire_lock(worker_id)
    if not lock_path:
        print(f"[{worker_id}] Another instance is already running. Exiting to prevent duplicates.", flush=True)
        sys.exit(0)
    
    pid_file = Path(__file__).parent / "daemon.pid"
    state_dir = Path(__file__).parent / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_file = state_dir / "current_task.json"
    
    if checkpoint_file.exists():
        print(f"[{worker_id}] Found uncompleted task checkpoint from previous crash. Deferring to Courier server as canonical authority.", flush=True)
        try:
            checkpoint_file.unlink()
        except OSError:
            pass
            
    try:
        print(f"[{worker_id}] Windows Worker HTTP Daemon started. PID={os.getpid()}", flush=True)
        
        backoff = 10
        max_backoff = 300
        
        while True:
            try:
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
                    print(f"[{worker_id}] Resource pressure high. Pausing claims.", flush=True)
                    time.sleep(60)
                    continue
                
                # 3. Claim Task
                req = urllib.request.Request(f"{API_URL}/tasks/claim", method="POST")
                for k, v in HEADERS.items(): req.add_header(k, v)
                res = urllib.request.urlopen(req, data=data, timeout=10)
                res_data = json.loads(res.read().decode("utf-8"))
                
                task = res_data.get("task")
                if task:
                    try:
                        checkpoint_file.write_text(json.dumps(task))
                    except Exception:
                        pass
                        
                    result = run_task(task, config)
                    http_post_result(result)
                    print(f"[{worker_id}] Task {task['task_id']} completed. Result posted.", flush=True)
                    
                    if checkpoint_file.exists():
                        try:
                            checkpoint_file.unlink()
                        except OSError:
                            pass
                    backoff = 10 # reset backoff on success
                else:
                    # Idle, reset backoff
                    backoff = 10
                    
            except Exception as e:
                print(f"[{worker_id}] Loop error: {e}. Backing off {backoff}s.", flush=True)
                time.sleep(backoff)
                backoff = min(max_backoff, backoff * 2)
                continue
                
            time.sleep(10)
            
    finally:
        if lock_path and os.path.exists(lock_path):
            try:
                os.remove(lock_path)
            except OSError:
                pass
        if pid_file.exists():
            try:
                pid_file.unlink()
            except OSError:
                pass

if __name__ == "__main__":
    loop()
