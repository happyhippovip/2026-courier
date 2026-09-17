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
    API_KEY = os.environ.get("COURIER_API_KEY") or _keyring.get_password("courier_worker", "COURIER_API_KEY")
except ImportError:
    API_KEY = os.environ.get("COURIER_API_KEY")

if not API_KEY:
    print("[Windows Worker] FATAL: No COURIER_API_KEY found in environment or OS keyring.", flush=True)
    print("[Windows Worker] Set via: $env:COURIER_API_KEY or keyring.set_password('courier_worker','courier_api_key','<key>')", flush=True)
    sys.exit(1)

print(f"[Windows Worker] Using API_KEY prefix: {API_KEY[:4]}...", flush=True)
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
        print(f"[{worker_id}] Registered successfully")
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
        except urllib.error.HTTPError as e:
            print(f"[Windows Worker] Failed to post result: {e} - {e.read().decode('utf-8')}")
            time.sleep(2 ** attempt)
        except Exception as e:
            print(f"[Windows Worker] Failed to post result: {e}")
            time.sleep(2 ** attempt)
    raise RuntimeError("Failed to post result after 5 attempts")

def run_task(task, config):
    print(f"[{config['WORKER_ID']}] Running task {task['task_id']}...")
    
    instruction = task.get("instruction", "")
    
    out_clean = ""
    stderr = ""
    run_id = "win-native"
    
    marker_path = Path(__file__).parent / "state" / "effect_marker.json"
    marker_path.parent.mkdir(exist_ok=True)
    with open(marker_path, "w") as f:
        json.dump(task, f)

    print(f"[{config['WORKER_ID']}] Executing native PowerShell instruction.")
    cmd = ["powershell", "-Command", instruction]
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, text=True, encoding='utf-8', errors='replace', creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        run_id = str(process.pid)
        stdout, stderr_out = process.communicate(timeout=600)
        out_clean = stdout.strip()
        stderr = stderr_out
        status = "SUCCESS" if process.returncode == 0 else "FAILED"
    except subprocess.TimeoutExpired as e:
        status = "FAILED"
        stderr = "TimeoutExpired: task exceeded 600s"
    except Exception as e:
        status = "FAILED"
        stderr = str(e)
    finally:
        # Exact process tree cleanup (no broad kills)
        try:
            if process.poll() is None:
                # /T kills the tree, /F forces, /PID targets exact process
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid, timeout=120)], capture_output=True)
        except Exception:
            pass
    
    if marker_path.exists():
        try:
            marker_path.unlink()
        except OSError:
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
        "execution_ref": task.get("execution_ref"),
        "worker_id": task.get("worker_id") or config["WORKER_ID"],
        "provider": "windows_native",
        "run_id": run_id,
        "result_id": f"result-{uuid.uuid4().hex}",
        "artifacts": artifacts if status == "SUCCESS" else []
    }
    if "batch_id" in task: res_json["batch_id"] = task["batch_id"]
    if "prompt_id" in task: res_json["prompt_id"] = task["prompt_id"]
    
    return res_json

import psutil

def is_resource_pressure_high(config=None):
    if config is None:
        config = load_config()
    profile = os.environ.get("WORKER_PROFILE", config.get("WORKER_PROFILE", "LOW_RESOURCE"))
    
    cpu_threshold = 100.0
    mem_threshold = 100.0
    if profile == "STANDARD":
        cpu_threshold = 95.0
        mem_threshold = 95.0
    elif profile == "HIGH_CAPACITY":
        cpu_threshold = 98.0
        mem_threshold = 98.0
        
    try:
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory().percent
    except Exception:
        cpu = 0.0
        mem = 0.0
        
    sim_cpu = float(os.environ.get("SIMULATE_CPU_PERCENT", -1))
    sim_mem = float(os.environ.get("SIMULATE_MEM_PERCENT", -1))
    
    if sim_cpu >= 0: cpu = sim_cpu
    if sim_mem >= 0: mem = sim_mem
    
    return cpu > cpu_threshold or mem > mem_threshold

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
            out_bytes = subprocess.check_output(["tasklist", "/FI", f"PID eq {pid}"])
            out = out_bytes.decode('utf-8', errors='ignore')
            if str(pid) not in out:
                # Stale lock
                os.remove(lock_file)
                return acquire_lock(worker_id)
        except Exception as e:
            print(f"[{worker_id}] Lock acquire failed: {e}")
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
        
        marker_path = Path(__file__).parent / "state" / "effect_marker.json"
        if marker_path.exists():
            try:
                with open(marker_path, "r") as f:
                    crashed_task = json.load(f)
                print(f"[{worker_id}] Found ambiguous crash marker for task {crashed_task.get('task_id')}")
                res_json = {
                    "status": "FAILED",
                    "stdout": "",
                    "stderr": "AMBIGUOUS_CRASH: Worker crashed during external effect.",
                    "goal_id": crashed_task.get("goal_id"),
                    "task_id": crashed_task.get("task_id"),
                    "attempt_id": crashed_task.get("attempt_id"),
                    "dispatch_id": crashed_task.get("dispatch_id"),
                    "execution_ref": crashed_task.get("execution_ref"),
                    "worker_id": worker_id,
                    "provider": "windows_native",
                    "run_id": "crashed-unknown",
                    "result_id": f"result-{uuid.uuid4().hex}",
                    "artifacts": []
                }
                if "batch_id" in crashed_task: res_json["batch_id"] = crashed_task["batch_id"]
                if "prompt_id" in crashed_task: res_json["prompt_id"] = crashed_task["prompt_id"]
                http_post_result(res_json)
            except Exception as e:
                print(f"[{worker_id}] Failed to report ambiguous crash: {e}")
            finally:
                try:
                    marker_path.unlink()
                except OSError:
                    pass
        
        error_backoff = 10
        max_error_backoff = 300
        
        idle_backoff = 5.0
        max_idle_backoff = 30.0
        
        while True:
            try:
                result_marker_path = Path(__file__).parent / "state" / "result_marker.json"
                if result_marker_path.exists():
                    try:
                        with open(result_marker_path, "r") as f:
                            saved_result = json.load(f)
                        print(f"[{worker_id}] Found unsent result marker for task {saved_result.get('task_id')}")
                        http_post_result(saved_result)
                    except Exception as e:
                        print(f"[{worker_id}] Failed to report saved result: {e}")
                        raise
                    try:
                        result_marker_path.unlink()
                    except OSError:
                        pass
                        
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
                if is_resource_pressure_high(config):
                    print(f"[{worker_id}] Resource pressure high. Pausing claims.")
                    time.sleep(5.0)
                    continue
                
                # 3. Claim Task
                req = urllib.request.Request(f"{API_URL}/tasks/claim", method="POST")
                for k, v in HEADERS.items(): req.add_header(k, v)
                res = urllib.request.urlopen(req, data=data, timeout=10)
                res_data = json.loads(res.read().decode("utf-8"))
                
                task = res_data.get("task")
                if task:
                    result = run_task(task, config)
                    
                    result_marker_path = Path(__file__).parent / "state" / "result_marker.json"
                    with open(result_marker_path, "w") as f:
                        json.dump(result, f)
                        
                    http_post_result(result)
                    print(f"[{worker_id}] Task {task['task_id']} completed. Result posted.")
                    
                    try:
                        result_marker_path.unlink()
                    except OSError:
                        pass
                        
                    error_backoff = 10
                    idle_backoff = 5.0
                else:
                    idle_backoff = min(max_idle_backoff, idle_backoff * 1.5)
                    
            except Exception as e:
                print(f"[{worker_id}] Loop error: {e}. Backing off {error_backoff}s.")
                time.sleep(error_backoff)
                error_backoff = min(max_error_backoff, error_backoff * 2)
                continue
                
            time.sleep(idle_backoff)
            
    finally:
        if os.path.exists(lock_path):
            os.remove(lock_path)

if __name__ == "__main__":
    loop()
