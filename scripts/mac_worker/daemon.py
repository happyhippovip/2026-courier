import json, time, os, sys, shutil, subprocess, uuid, traceback
from pathlib import Path
import urllib.request
import urllib.error
import urllib.parse

# Paths
BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
STATE_DIR = BASE_DIR / "state"
LOGS_DIR = BASE_DIR / "logs"

def load_config():
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)
    
    # Try reading from macOS keychain
    try:
        pw = subprocess.check_output(["security", "find-generic-password", "-a", "courier_worker", "-s", "courier_api_key", "-w"], stderr=subprocess.DEVNULL)
        config["COURIER_API_KEY"] = pw.decode("utf-8").strip()
    except subprocess.CalledProcessError:
        pass
        
    try:
        srv = subprocess.check_output(["security", "find-generic-password", "-a", "courier_worker", "-s", "courier_server_url", "-w"], stderr=subprocess.DEVNULL)
        config["COURIER_SERVER"] = srv.decode("utf-8").strip()
    except subprocess.CalledProcessError:
        pass
    
    # Environment overrides
    if "COURIER_SERVER" in os.environ:
        config["COURIER_SERVER"] = os.environ["COURIER_SERVER"]
    if "COURIER_API_KEY" in os.environ:
        config["COURIER_API_KEY"] = os.environ["COURIER_API_KEY"]
        
    return config

def write_log(msg):
    print(msg)
    with open(LOGS_DIR / "worker.log", "a") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")

def http_post(config, endpoint, data):
    url = config["COURIER_SERVER"].rstrip("/") + endpoint
    req = urllib.request.Request(url, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {config.get('COURIER_API_KEY', '')}")
    
    jsondata = json.dumps(data).encode("utf-8")
    
    try:
        with urllib.request.urlopen(req, data=jsondata, timeout=10) as response:
            return json.loads(response.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        return None, f"HTTP Error {e.code}: {err_msg}"
    except Exception as e:
        return None, str(e)

def run_native(task, config):
    write_log(f"Running NATIVE task {task['task_id']}")
    instruction = task.get('instruction', task.get('description', ''))
    
    # ALLOWLIST CHECK
    action = task.get("action", "").lower()
    allowed_actions = ["create_file", "read_file_metadata", "git_status", "run_known_test", "hash_file", "echo"]
    
    # For backward compatibility with the canary, we parse "echo" if it's the first word of instruction
    if not action:
        first_word = instruction.split()[0].lower() if instruction else ""
        if first_word in allowed_actions:
            action = first_word
            
    if action not in allowed_actions:
        write_log(f"NATIVE action '{action}' rejected. Not in allowlist.")
        return {
            "status": "FAILED",
            "stderr": f"Native action '{action}' is not allowed for security reasons.",
            "execution_mode": "NATIVE"
        }
        
    # Safe bounded execution
    try:
        if action == "echo":
            result = subprocess.run(instruction, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, executable="/bin/bash")
        elif action == "git_status":
            result = subprocess.run(["git", "status"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        else:
            return {"status": "FAILED", "stderr": f"Action '{action}' is allowed but handler is not implemented yet.", "execution_mode": "NATIVE"}
            
        return {
            "status": "SUCCESS" if result.returncode == 0 else "FAILED",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
            "execution_mode": "NATIVE"
        }
    except Exception as e:
        return {"status": "FAILED", "stderr": str(e), "execution_mode": "NATIVE"}

def run_agy(task, config):
    write_log(f"Running AI task {task['task_id']} via agy")
    instruction = task.get('instruction', task.get('description', ''))
    
    prompt = f"Task ID: {task['task_id']}\nInstruction: {instruction}\n\nYou are a headless worker on Mac. You MUST execute the instruction. After you have successfully executed the instruction, you MUST output a final JSON object in a markdown codeblock. The JSON must contain a 'status' field set to 'SUCCESS' and a 'stdout_summary' field explaining what you did. IMPORTANT: Your current working directory is {os.getcwd()}. Any file artifacts you create MUST be relative to this directory."
    agy_bin = shutil.which("agy") or shutil.which("agy", path=os.environ.get("PATH", "") + ":/Users/user/.local/bin:/usr/local/bin:/opt/homebrew/bin")
    if not agy_bin:
        return {"status": "FAILED", "reason": "AGY_NOT_FOUND", "execution_mode": "ANTIGRAVITY"}
        
    wrapper = os.path.join(os.path.dirname(__file__), "limit_wrapper.sh")
    cmd = [wrapper, agy_bin, "-p", prompt, "--dangerously-skip-permissions"]
    
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate(timeout=300)
        
        out_clean = stdout.strip()
        parsed = False
        res_json = {}
        if "```json" in out_clean:
            try:
                ext = out_clean.split("```json")[1].split("```")[0].strip()
                res_json = json.loads(ext)
                parsed = True
            except:
                pass
        
        res_json["execution_mode"] = "ANTIGRAVITY"
        res_json["stderr"] = stderr
        if not parsed:
            res_json["status"] = "FAILED"
            res_json["raw_diagnostic"] = out_clean
            
        return res_json
        
    except Exception as e:
        return {"status": "FAILED", "stderr": str(e), "execution_mode": "ANTIGRAVITY"}

def loop():
    write_log("Starting Mac Worker HTTP Daemon...")
    config = load_config()
    current_task_state_file = STATE_DIR / "current_task.json"
    current_result_state_file = STATE_DIR / "current_result.json"
    
    # Load previously claimed task for duplicate protection
    task = None
    if current_task_state_file.exists():
        write_log("Found unfinished task from previous run, resuming...")
        with open(current_task_state_file, 'r') as f:
            task = json.load(f)
            
    # Load pending result if execution finished but delivery failed
    pending_result = None
    if current_result_state_file.exists():
        write_log("Found pending result from previous run, resuming delivery...")
        with open(current_result_state_file, 'r') as f:
            pending_result = json.load(f)

    registered = False
    
    while True:
        try:
            if not registered:
                reg_payload = {
                    "worker_id": config["WORKER_ID"],
                    "platform": "macos",
                    "capabilities": ["macos", "linux", "antigravity"]
                }
                res, err = http_post(config, "/workers/register", reg_payload)
                if err:
                    write_log(f"Failed to register: {err}")
                    time.sleep(5) # backoff
                    continue
                write_log("Registered successfully.")
                registered = True
                
            # Heartbeat
            res, err = http_post(config, "/workers/heartbeat", {"worker_id": config["WORKER_ID"]})
            if err:
                write_log(f"Heartbeat failed: {err}")
                registered = False
                time.sleep(5)
                continue
                
            if not task and not pending_result:
                # Claim Task
                res, err = http_post(config, "/tasks/claim", {"worker_id": config["WORKER_ID"]})
                if err:
                    write_log(f"Claim failed: {err}")
                    time.sleep(5)
                    continue
                    
                task = res.get("task")
                if task:
                    with open(current_task_state_file, 'w') as f:
                        json.dump(task, f)
                else:
                    time.sleep(config.get('IDLE_POLL_INTERVAL_SECONDS', 30))
                    continue
                        
            if task and not pending_result:
                write_log(f"Processing task {task['task_id']}")
                keep_awake = subprocess.Popen(["caffeinate", "-s", "-i"])
                try:
                    mode = task.get("mode", "ANTIGRAVITY")
                    # Fallback to NATIVE if requested via target_agent routing
                    target = task.get("target_agent", "").lower()
                    if "mac" in target and mode == "ANTIGRAVITY" and "echo" in task.get("instruction", "").lower():
                        # For simple testing/canary routing we force NATIVE if they specify echo
                        mode = "NATIVE"

                    if mode == "NATIVE":
                        result = run_native(task, config)
                    else:
                        result = run_agy(task, config)
                    
                    # Format result payload
    # Form valid artifacts structure
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
                        "run_id": str(uuid.uuid4()),
                        "result_id": str(uuid.uuid4()),
                        "status": result.get("status", "FAILED"),
                        "artifacts": artifact_evidence,
                        "provider": "mac_" + result.get("execution_mode", "unknown").lower(),
                        "raw_result": result
                    }
                    
                    # Persist pending result before attempting to send
                    with open(current_result_state_file, 'w') as f:
                        json.dump(payload, f)
                    pending_result = payload
                    
                finally:
                    keep_awake.terminate()
            
            if pending_result:
                # Backoff loop for posting result
                res, err = http_post(config, "/tasks/result", pending_result)
                if err:
                    write_log(f"Result post failed: {err}. Will retry on next loop.")
                    time.sleep(5)
                    continue
                else:
                    write_log(f"Result posted successfully: {res}")
                    if current_result_state_file.exists():
                        os.remove(current_result_state_file)
                    if current_task_state_file.exists():
                        os.remove(current_task_state_file)
                    pending_result = None
                    task = None
                
        except Exception as e:
            write_log(f"Error in HTTP poll loop: {e}\n{traceback.format_exc()}")
            
        time.sleep(config.get("POLL_INTERVAL_SECONDS", 5))

if __name__ == "__main__":
    loop()
