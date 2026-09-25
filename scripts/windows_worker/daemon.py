import json, time, os, sys, shutil, subprocess
from pathlib import Path
import urllib.request
import urllib.error
import tempfile

API_URL = "http://192.168.178.162:8080"
API_KEY = "prod-secret-12345"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def load_config():
    config_path = Path(__file__).parent / "config.json"
    with open(config_path, "r") as f:
        return json.load(f)

def register_worker(worker_id):
    req = urllib.request.Request(f"{API_URL}/workers/register", method="POST")
    for k, v in HEADERS.items(): req.add_header(k, v)
    data = json.dumps({"worker_id": worker_id, "platform": "windows", "capabilities": ["windows"]}).encode("utf-8")
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
    worker_id = config["WORKER_ID"]
    
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
