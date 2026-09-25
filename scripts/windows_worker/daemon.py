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
    API_KEY = os.environ.get("COURIER_API_KEY") or _keyring.get_password("courier_worker", "courier_api_key") or _keyring.get_password("courier_worker", "COURIER_API_KEY")
except ImportError:
    API_KEY = os.environ.get("COURIER_API_KEY")

if not API_KEY:
    print("[Windows Worker] FATAL: No COURIER_API_KEY found in environment or OS keyring.", flush=True)
    print("[Windows Worker] Set via: $env:COURIER_API_KEY or keyring.set_password('courier_worker','courier_api_key','<key>')", flush=True)
    sys.exit(1)

print("[Windows Worker] Using API_KEY (redacted)", flush=True)
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def register_worker(worker_id):
    req = urllib.request.Request(f"{API_URL}/workers/register", method="POST")
    for k, v in HEADERS.items(): req.add_header(k, v)
    cost_class = os.environ.get("WORKER_COST_CLASS", "low")
    
    runtime_sha = "unknown"
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
        runtime_sha = out.decode("utf-8").strip()
    except Exception:
        pass

    payload = {
        "worker_id": worker_id, 
        "platform": "windows", 
        "capabilities": ["windows"], 
        "cost_class": cost_class,
        "runtime_sha": runtime_sha
    }
    data = json.dumps(payload).encode("utf-8")
    try:
        urllib.request.urlopen(req, data=data, timeout=10)
        print(f"[{worker_id}] Registered successfully (SHA: {runtime_sha[:8]})")
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
            try:
                body = e.read().decode('utf-8')
                data = json.loads(body)
                if e.code in (200, 409) and data.get("status") == "ACK_DUPLICATE":
                    print(f"[Windows Worker] Result already acknowledged by server: {body}")
                    return
                elif e.code == 409 and data.get("reason") == "CONTRADICTORY_DUPLICATE":
                    print(f"[Windows Worker] Result rejected as contradictory duplicate: {body}")
                    return
                elif e.code == 409 and "Task is not awaiting a result" in body:
                    print(f"[Windows Worker] Result rejected (task no longer active): {body}")
                    return
            except Exception:
                body = ""
            print(f"[Windows Worker] Failed to post result: {e} - {body}")
            time.sleep(2 ** attempt)
        except Exception as e:
            print(f"[Windows Worker] Failed to post result: {e}")
            time.sleep(2 ** attempt)
    raise RuntimeError("Failed to post result after 5 attempts")


def generate_result_id(res):
    identity = {
        "goal_id": res.get("goal_id"),
        "task_id": res.get("task_id"),
        "attempt_id": res.get("attempt_id"),
        "dispatch_id": res.get("dispatch_id"),
        "execution_ref": res.get("execution_ref"),
        "worker_id": res.get("worker_id"),
        "run_id": res.get("run_id"),
        "status": res.get("status"),
        "artifacts": res.get("artifacts", []),
        "runtime_identity": res.get("runtime_identity")
    }
    if "batch_id" in res:
        identity["batch_id"] = res["batch_id"]
    if "prompt_id" in res:
        identity["prompt_id"] = res["prompt_id"]
    encoded = json.dumps(identity, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return "result-" + hashlib.sha256(encoded).hexdigest()

def run_task(task, config):
    print(f"[{config['WORKER_ID']}] Running task {task['task_id']}...")
    
    instruction = task.get("instruction", "")
    
    # WAITING_PROVIDER isolation
    action = task.get("action", "").lower()
    if action == "provider_wait":
        print(f"[{config['WORKER_ID']}] Simulating PROVIDER_WAIT")
        res_json = {
            "status": "PROVIDER_WAIT",
            "reason": "SIMULATED_429_RATE_LIMIT",
            "stdout": "",
            "stderr": "",
            "goal_id": task.get("goal_id"),
            "task_id": task.get("task_id"),
            "attempt_id": task.get("attempt_id"),
            "dispatch_id": task.get("dispatch_id"),
            "execution_ref": task.get("execution_ref"),
            "worker_id": task.get("worker_id") or os.environ.get("COURIER_WORKER_ID") or config.get("WORKER_ID", "default-win-worker"),
            "provider": "windows_native",
            "runtime_identity": task.get("server_binding"),
            "run_id": "win-native",
            "result_id": f"result-{uuid.uuid4().hex}",
            "artifacts": []
        }
        if "batch_id" in task: res_json["batch_id"] = task["batch_id"]
        if "prompt_id" in task: res_json["prompt_id"] = task["prompt_id"]
        res_json["result_id"] = generate_result_id(res_json)
        return res_json

    out_clean = ""
    stderr = ""
    run_id = "win-native"
    
    marker_path = Path(__file__).parent / "state" / "effect_marker.json"
    marker_path.parent.mkdir(exist_ok=True)
    with open(marker_path, "w") as f:
        json.dump(task, f)

    cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", "-"]
    try:
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if hasattr(subprocess, 'CREATE_NEW_PROCESS_GROUP') else 0
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', creationflags=flags)
        run_id = str(process.pid)
        stdout, stderr_out = process.communicate(input=instruction, timeout=600)
        out_clean = stdout.strip()
        stderr = stderr_out
        status = "SUCCESS" if process.returncode == 0 else "FAILED"
        
        combined_out = (out_clean + " " + stderr).lower()
        if any(kw in combined_out for kw in ["429", "too many requests", "quota", "rate limit", "resource exhausted", "provider unavailable", "500", "502", "503", "504", "timeout", "timed out", "internal server error", "service unavailable", "bad gateway", "401", "403", "unauthorized", "authentication failed", "invalid api key"]):
            status = "PROVIDER_WAIT"
            
    except subprocess.TimeoutExpired as e:
        status = "FAILED"
        stderr = "TimeoutExpired: task exceeded 600s"
    except Exception as e:
        status = "FAILED"
        stderr = str(e)
    finally:
        # Exact process tree cleanup (no broad kills) using psutil for reliability on Windows
        try:
            import psutil
            try:
                parent = psutil.Process(process.pid)
                for child in parent.children(recursive=True):
                    try:
                        child.kill()
                    except psutil.NoSuchProcess:
                        pass
                parent.kill()
            except psutil.NoSuchProcess:
                pass
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
        "worker_id": task.get("worker_id") or os.environ.get("COURIER_WORKER_ID") or config.get("WORKER_ID", "default-win-worker"),
        "provider": "windows_native",
            "runtime_identity": task.get("server_binding"),
        "run_id": run_id,
        "result_id": f"result-{uuid.uuid4().hex}",
        "artifacts": artifacts if status == "SUCCESS" else []
    }
    if status == "PROVIDER_WAIT":
        res_json["reason"] = "QUOTA_OR_RATE_LIMIT"
        
    if "batch_id" in task: res_json["batch_id"] = task["batch_id"]
    if "prompt_id" in task: res_json["prompt_id"] = task["prompt_id"]
    
    res_json["result_id"] = generate_result_id(res_json)
    
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
        lock_data = {
            "service_id": "courier-windows-worker",
            "worker_id": worker_id,
            "pid": os.getpid(),
            "process_create_time": psutil.Process(os.getpid()).create_time(),
            "executable": sys.executable,
            "daemon_path": str(Path(__file__).absolute()),
            "started_at": time.time()
        }
        os.write(fd, json.dumps(lock_data).encode("utf-8"))
        os.close(fd)
        return lock_file
    except FileExistsError:
        # Check if the process is actually running
        try:
            with open(lock_file, "r") as f:
                data = f.read().strip()
            if not data:
                raise ValueError("Empty lock file")
            try:
                lock_data = json.loads(data)
                pid = lock_data["pid"]
                create_time = lock_data.get("process_create_time")
            except ValueError:
                pid = int(data)
                create_time = None

            # Cross-platform process existence check
            try:
                p = psutil.Process(pid)
                if create_time is not None:
                    if abs(p.create_time() - create_time) > 0.1:
                        raise psutil.NoSuchProcess(pid)
            except (psutil.NoSuchProcess, ProcessLookupError, OSError):
                # Stale lock - process not running
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
            "runtime_identity": crashed_task.get("server_binding"),
                    "run_id": "crashed-unknown",
                    "result_id": f"result-{uuid.uuid4().hex}",
                    "artifacts": []
                }
                if "batch_id" in crashed_task: res_json["batch_id"] = crashed_task["batch_id"]
                res_json["result_id"] = generate_result_id(res_json)
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
                pause_marker_path = Path(__file__).parent / "state" / "pause.marker"
                stop_marker_path = Path(__file__).parent / "state" / "stop.marker"
                
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
                        
                if stop_marker_path.exists():
                    print(f"[{worker_id}] Stop marker found. Exiting gracefully after current task.")
                    break
                    
                if pause_marker_path.exists():
                    print(f"[{worker_id}] Pause marker found. Pausing claims.")
                    time.sleep(5.0)
                    continue

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
