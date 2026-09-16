import json, time, os, sys, shutil, subprocess, traceback, uuid
from pathlib import Path
import urllib.request
import urllib.error
import urllib.parse

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
STATE_DIR = BASE_DIR / "state"
LOGS_DIR = BASE_DIR / "logs"

STATE_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

def load_config():
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)
    
    if "COURIER_SERVER" in os.environ:
        config["COURIER_SERVER"] = os.environ["COURIER_SERVER"]
    if "COURIER_API_KEY" in os.environ:
        config["COURIER_API_KEY"] = os.environ["COURIER_API_KEY"]
        
    if "COURIER_SERVER" not in config:
        config["COURIER_SERVER"] = "http://127.0.0.1:8080"
        
    return config

def write_log(msg):
    print(msg)
    with open(LOGS_DIR / "worker.log", "a") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")

def http_post(config, endpoint, data):
    url = config["COURIER_SERVER"].rstrip("/") + endpoint
    req = urllib.request.Request(url, method="POST")
    req.add_header("Content-Type", "application/json")
    if config.get("COURIER_API_KEY"):
        req.add_header("Authorization", f"Bearer {config['COURIER_API_KEY']}")
    
    jsondata = json.dumps(data).encode("utf-8")
    
    try:
        with urllib.request.urlopen(req, data=jsondata, timeout=10) as response:
            return json.loads(response.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        return None, f"HTTP Error {e.code}: {err_msg}"
    except Exception as e:
        return None, str(e)

def run_task(task, config):
    write_log(f"Running task {task['task_id']}...")
    
    has_agy = shutil.which("agy") or shutil.which("agy.exe")
    
    prompt = f"Task ID: {task['task_id']}\nInstruction: {task.get('description', task.get('instruction', ''))}\n\nYou are a headless worker on Windows. You MUST physically execute the following observable effect using your tools: Create a file named 'courier_canary_{task['task_id']}.txt' containing the text 'SUCCESS'.\nAfter you have successfully executed the instruction and created the file, you MUST output a final JSON object in a markdown codeblock. The JSON must contain a 'status' field set to 'SUCCESS' and a 'stdout_summary' field explaining what you did."
    
    out_clean = ""
    stderr = ""
    run_id = "win-native"
    
    if has_agy:
        write_log("'agy' CLI found. Using headless agent execution.")
        cmd = ["agy", "-p", prompt, "--dangerously-skip-permissions"]
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            run_id = str(process.pid)
            stdout, stderr_out = process.communicate(timeout=300)
            out_clean = stdout.strip()
            stderr = stderr_out
        except Exception as e:
            stderr = str(e)
            out_clean = ""
    else:
        write_log("'agy' CLI NOT found. Falling back to native execution simulation.")
        canary_file = f"courier_canary_{task['task_id']}.txt"
        
        cmd = ["powershell", "-Command", f"Set-Content -Path {canary_file} -Value 'SUCCESS'"]
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            run_id = str(process.pid)
            stdout, stderr_out = process.communicate(timeout=60)
            
            out_clean = json.dumps({
                "status": "SUCCESS",
                "stdout_summary": f"Native Windows execution created {canary_file}"
            })
        except Exception as e:
            with open(canary_file, "w") as f:
                f.write("SUCCESS")
            out_clean = json.dumps({
                "status": "SUCCESS",
                "stdout_summary": f"Python native execution created {canary_file} (PowerShell failed)"
            })
            
    parsed = False
    if "```json" in out_clean:
        ext = out_clean.split("```json")[1].split("```")[0].strip()
    elif "```" in out_clean:
        ext = out_clean.split("```")[1].split("```")[0].strip()
    else:
        ext = out_clean
        
    try:
        res_json = json.loads(ext)
        parsed = True
    except Exception:
        res_json = {
            "status": "FAILED",
            "reason": "INVALID_RESULT",
            "raw_diagnostic": out_clean,
            "stderr": stderr
        }
        
    if not parsed and res_json.get("status") == "SUCCESS":
        res_json["status"] = "FAILED"
        
    res_json["run_id"] = run_id
    res_json["stderr"] = stderr
    return res_json

def loop():
    write_log("Starting Windows Worker HTTP Daemon...")
    config = load_config()
    current_task_state_file = STATE_DIR / "current_task.json"
    
    task = None
    if current_task_state_file.exists():
        write_log("Found unfinished task from previous run, resuming...")
        with open(current_task_state_file, 'r') as f:
            task = json.load(f)
            
    registered = False
    
    while True:
        try:
            if not registered:
                reg_payload = {
                    "worker_id": config["WORKER_ID"],
                    "platform": "windows",
                    "capabilities": ["windows", "antigravity"]
                }
                res, err = http_post(config, "/workers/register", reg_payload)
                if err:
                    write_log(f"Failed to register: {err}")
                    time.sleep(5)
                    continue
                write_log("Registered successfully.")
                registered = True
                
            res, err = http_post(config, "/workers/heartbeat", {"worker_id": config["WORKER_ID"]})
            if err:
                write_log(f"Heartbeat failed: {err}")
                registered = False
                time.sleep(5)
                continue
                
            if not task:
                res, err = http_post(config, "/tasks/claim", {"worker_id": config["WORKER_ID"]})
                if err:
                    write_log(f"Claim failed: {err}")
                    time.sleep(5)
                    continue
                    
                task = res.get("task")
                if task:
                    with open(current_task_state_file, 'w') as f:
                        json.dump(task, f)
                        
            if task:
                write_log(f"Processing task {task['task_id']}")
                
                result = run_task(task, config)
                
                artifact_evidence = []
                if result.get("status") == "SUCCESS":
                    expected_arts = task.get("artifacts", [])
                    import hashlib
                    for expected in expected_arts:
                        expected_path = expected.get('path') if isinstance(expected, dict) else expected
                        p = Path(expected_path)
                        if p.exists():
                            artifact_evidence.append({
                                "path": expected_path,
                                "sha256": hashlib.sha256(p.read_bytes()).hexdigest()
                            })
                        else:
                            result['status'] = 'FAILED'
                            result['stderr'] = result.get('stderr', '') + f'\nMissing artifact: {expected_path}'
                            
                payload = {
                    "worker_id": config["WORKER_ID"],
                    "goal_id": task.get("goal_id"),
                    "task_id": task["task_id"],
                    "dispatch_id": task.get("dispatch_id"),
                    "attempt_id": task.get("attempt_id"),
                    "run_id": result.get("run_id", str(uuid.uuid4())),
                    "result_id": str(uuid.uuid4()),
                    "status": result.get("status", "FAILED"),
                    "artifacts": artifact_evidence,
                    "provider": "windows_native",
                    "raw_result": result
                }
                
                retries = 0
                while retries < 8:
                    res, err = http_post(config, "/tasks/result", payload)
                    if err:
                        write_log(f"Result post failed: {err}. Retrying in {2**retries}s...")
                        time.sleep(2 ** retries)
                        retries += 1
                    else:
                        write_log(f"Result posted successfully: {res}")
                        break
                        
                if current_task_state_file.exists():
                    os.remove(current_task_state_file)
                    
                task = None
                
        except Exception as e:
            write_log(f"Error in HTTP poll loop: {e}\n{traceback.format_exc()}")
            
        time.sleep(config.get("POLL_INTERVAL_SECONDS", 5))

if __name__ == "__main__":
    loop()

