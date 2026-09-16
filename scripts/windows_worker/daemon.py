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
except ImportError:
    API_KEY = os.environ.get("COURIER_API_KEY")

if not API_KEY:
    print("[Windows Worker] FATAL: No COURIER_API_KEY found in environment or OS keyring.", flush=True)
    print("[Windows Worker] Set via: $env:COURIER_API_KEY or keyring.set_password('courier_worker','courier_api_key','<key>')", flush=True)
    sys.exit(1)
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
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
            return
        except Exception as e:
            print(f"[Windows Worker] Failed to post result: {e}")
            time.sleep(2 ** attempt)

def run_task(task, config):
    print(f"[{config['WORKER_ID']}] Running task {task['task_id']}...")
    
    instruction = task.get("instruction", "")
    
    out_clean = ""
    stderr = ""
    run_id = "win-native"
    
    print(f"[{config['WORKER_ID']}] Executing native PowerShell instruction.")
    cmd = ["powershell", "-Command", instruction]
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        run_id = str(process.pid)
        stdout, stderr_out = process.communicate(timeout=600)
        out_clean = stdout.strip()
        stderr = stderr_out
        status = "SUCCESS" if process.returncode == 0 else "FAILED"
    except subprocess.TimeoutExpired:
        status = "FAILED"
        stderr = "Timeout of 600s exceeded. Exact child process tree terminated."
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True)
    except Exception as e:
        status = "FAILED"
        stderr = str(e)
            
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
    worker_id = os.environ.get("COURIER_WORKER_ID") or config.get("WORKER_ID", "default-win-worker")
    
    lock_path = acquire_lock(worker_id)
    if not lock_path:
        print(f"[{worker_id}] Another instance is already running. Exiting to prevent duplicates.")
        sys.exit(0)
    
    try:
        print(f"[{worker_id}] Windows Worker HTTP Daemon started. PID={os.getpid()}")
        
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
                    print(f"[{worker_id}] Resource pressure high. Pausing claims.")
                    time.sleep(60)
                    continue
                
                # 3. Claim Task
                req = urllib.request.Request(f"{API_URL}/tasks/claim", method="POST")
                for k, v in HEADERS.items(): req.add_header(k, v)
                res = urllib.request.urlopen(req, data=data, timeout=10)
                res_data = json.loads(res.read().decode("utf-8"))
                
                task = res_data.get("task")
                if task:
                    result = run_task(task, config)
                    http_post_result(result)
                    print(f"[{worker_id}] Task {task['task_id']} completed. Result posted.")
                    backoff = 10 # reset backoff on success
                else:
                    # Idle, reset backoff
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
    loop()
