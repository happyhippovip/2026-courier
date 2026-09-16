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
LOGS_DIR.mkdir(parents=True, exist_ok=True)
STATE_DIR.mkdir(parents=True, exist_ok=True)
SECRET_KEY = None

def load_config():
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)
        
    if config.get("WORKER_ID") in ["test-mac", "", None]:
        import socket, uuid
        config["WORKER_ID"] = f"MAC-{socket.gethostname().split('.')[0].upper()}-{uuid.uuid4().hex[:6].upper()}"
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f)

    
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
    if not config.get('COURIER_API_KEY'):
        import sys; sys.stderr.write('FATAL: Missing credentials fail closed.\n'); sys.exit(1)
    if not config.get('COURIER_SERVER'):
        import sys; sys.stderr.write('FATAL: Missing server fail closed.\n'); sys.exit(1)
    global SECRET_KEY
    SECRET_KEY = config['COURIER_API_KEY']
        
    return config

def write_log(msg):
    # Rotate log if > 5MB
    log_file = LOGS_DIR / "worker.log"
    if log_file.exists() and log_file.stat().st_size > 5 * 1024 * 1024:
        log_file.rename(LOGS_DIR / "worker.log.1")
        
    print(msg)
    # Strip any potential secrets
    safe_msg = str(msg).replace(SECRET_KEY, '[REDACTED]') if SECRET_KEY else str(msg).replace(os.environ.get('COURIER_API_KEY', 'dummy'), '[REDACTED]')
    with open(log_file, "a") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {safe_msg}\n")

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
    allowed_actions = ["git_status", "echo"]
    
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
        import shlex
        if action == "echo":
            try:
                args = shlex.split(instruction)
            except ValueError as e:
                return {"status": "FAILED", "stderr": f"Malformed args: {e}", "execution_mode": "NATIVE"}
                
            if not args or args[0].lower() != "echo":
                return {"status": "FAILED", "stderr": "Malformed echo command.", "execution_mode": "NATIVE"}
            
            # Ban shell-injection-like input and path escape patterns
            for arg in args:
                if any(bad in arg for bad in [';', '|', '&', '>', '<', '$', '..', '`']):
                    return {"status": "FAILED", "stderr": "Shell operators and path escapes are banned.", "execution_mode": "NATIVE"}

            result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=False)
            
        elif action == "git_status":
            result = subprocess.run(["git", "status"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=False)
            
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
        try:
            stdout, stderr = process.communicate(timeout=300)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            return {"status": "FAILED", "stderr": "Execution timed out", "execution_mode": "ANTIGRAVITY"}
        
        # Enforce stdout/stderr payload limits
        if stdout and len(stdout) > 50000:
            stdout = "...[TRUNCATED]..." + stdout[-50000:]
        if stderr and len(stderr) > 20000:
            stderr = "...[TRUNCATED]..." + stderr[-20000:]
            
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
        res_json["exit_code"] = process.returncode
        
        # Check for provider unavailable / quota
        combined_out = (out_clean + " " + stderr).lower()
        if any(kw in combined_out for kw in ["429", "too many requests", "quota", "rate limit", "resource exhausted", "provider unavailable"]):
            res_json["status"] = "PROVIDER_WAIT"
            res_json["reason"] = "QUOTA_OR_RATE_LIMIT"
            return res_json

        if not parsed:
            res_json["status"] = "FAILED"
            res_json["raw_diagnostic"] = out_clean
            
        return res_json
        
    except Exception as e:
        return {"status": "FAILED", "stderr": str(e), "execution_mode": "ANTIGRAVITY"}


def run_copilot(task, config):
    write_log(f"Running AI task {task['task_id']} via Copilot CLI")
    instruction = task.get('instruction', task.get('description', ''))
    
    prompt = f"Task ID: {task['task_id']}\nInstruction: {instruction}"
    
    wrapper = os.path.join(os.path.dirname(__file__), "limit_wrapper.sh")
    
    import shutil
    gh_bin = shutil.which("gh")
    if not gh_bin:
        return {"status": "FAILED", "reason": "GH_NOT_FOUND", "execution_mode": "COPILOT"}
        
    cmd = [wrapper, gh_bin, "copilot", "suggest", "-t", "shell", prompt]
    
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            stdout, stderr = process.communicate(timeout=300)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            return {"status": "FAILED", "stderr": "Execution timed out", "execution_mode": "COPILOT"}
        
        # Enforce stdout/stderr payload limits
        if stdout and len(stdout) > 50000:
            stdout = "...[TRUNCATED]..." + stdout[-50000:]
        if stderr and len(stderr) > 20000:
            stderr = "...[TRUNCATED]..." + stderr[-20000:]
            
        combined_out = (stdout + " " + stderr).lower()
        if any(kw in combined_out for kw in ["429", "too many requests", "quota", "rate limit", "resource exhausted", "provider unavailable"]):
            return {
                "status": "PROVIDER_WAIT",
                "reason": "QUOTA_OR_RATE_LIMIT",
                "execution_mode": "COPILOT"
            }

        # We can't really execute gh copilot suggest automatically if it requires interactive confirmation,
        # but if we just want to return the output:
        res_json = {
            "status": "SUCCESS" if process.returncode == 0 else "FAILED",
            "stdout": stdout.strip(),
            "stderr": stderr.strip(),
            "execution_mode": "COPILOT"
        }
            
        return res_json
        
    except Exception as e:
        return {"status": "FAILED", "stderr": str(e), "execution_mode": "COPILOT"}

def loop():
    config = load_config()
    write_log("Starting Mac Worker HTTP Daemon...")
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
            
    pending_provider_wait = None
    current_wait_state_file = STATE_DIR / "current_provider_wait.json"
    if current_wait_state_file.exists():
        write_log("Found pending provider wait from previous run...")
        with open(current_wait_state_file, 'r') as f:
            pending_provider_wait = json.load(f)

    registered = False
    
    while True:
        try:
            if not registered:
                # Detect provider capabilities
                caps = ["macos", "linux"]
                
                # Check agy
                import shutil
                if shutil.which("agy") or shutil.which("agy", path="/Users/user/.local/bin:/usr/local/bin:/opt/homebrew/bin"):
                    caps.append("antigravity")
                    
                # Check gh copilot
                if shutil.which("gh") and "copilot" in subprocess.getoutput("gh extension list"):
                    caps.append("copilot")

                reg_payload = {
                    "worker_id": config["WORKER_ID"],
                    "platform": "macos",
                    "capabilities": caps
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
                task_id = task.get("task_id", "UNKNOWN")
                write_log(f"Processing task {task_id}")
                keep_awake = subprocess.Popen(["caffeinate", "-s", "-i"])
                try:
                    mode = task.get("mode", "ANTIGRAVITY")
                    result = None
                    
                    # 1. Structural Validation
                    if not task.get("task_id") or (not task.get("instruction") and not task.get("description")):
                        result = {"status": "FAILED", "reason": "MALFORMED_TASK", "stderr": "Task is missing task_id or instruction"}
                        mode = "FAILED_VALIDATION"
                        
                    # 2. Scope / Target Validation
                    target_agent = task.get("target_agent", "").lower()
                    target_capability = task.get("target_capability", "").lower()
                    if target_agent and "mac" not in target_agent and "night-captain" not in target_agent:
                        result = {"status": "FAILED", "reason": "UNQUALIFIED", "stderr": f"Target agent '{target_agent}' incompatible with Mac worker."}
                        mode = "FAILED_VALIDATION"
                    elif target_capability and target_capability not in ["", "mac", "macos", "antigravity", "linux", "copilot", "bash", "python"]:
                        result = {"status": "FAILED", "reason": "UNQUALIFIED", "stderr": f"Target capability '{target_capability}' missing on this worker."}
                        mode = "FAILED_VALIDATION"
                        
                    # 3. Workspace Validation
                    workspace = task.get("workspace")
                    if workspace and mode != "FAILED_VALIDATION":
                        try:
                            os.chdir(workspace)
                        except FileNotFoundError:
                            result = {"status": "FAILED", "reason": "FAILED_SCOPE", "stderr": f"Workspace {workspace} not found. Out of scope."}
                            mode = "FAILED_VALIDATION"

                    # 4. Routing
                    if mode != "FAILED_VALIDATION":
                        if "mac" in target_agent and mode == "ANTIGRAVITY" and "echo" in task.get("instruction", "").lower():
                            mode = "NATIVE"
                            
                        if mode == "NATIVE":
                            result = run_native(task, config)
                        elif mode == "COPILOT":
                            result = run_copilot(task, config)
                        else:
                            result = run_agy(task, config)
                    
                    # Handle Provider Wait

                    
                    if result.get("status") == "PROVIDER_WAIT":

                    
                        write_log(f"Task {task['task_id']} hit a provider wait: {result.get('reason')}")

                    
                        wait_payload = {

                    
                            "worker_id": config["WORKER_ID"],

                    
                            "reason": result.get("reason", "PROVIDER_UNAVAILABLE"),

                    
                            "wait_type": "WAITING_PROVIDER",

                    
                            "task_id": task["task_id"]

                    
                        }

                    
                        with open(STATE_DIR / "current_provider_wait.json", "w") as fw:

                    
                            json.dump(wait_payload, fw)

                    
                        if current_task_state_file.exists():

                    
                            current_task_state_file.unlink()

                    
                        task = None

                    
                        continue


                    
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
            
            if pending_provider_wait:
                res, err = http_post(config, f"/tasks/{pending_provider_wait['task_id']}/provider_wait", pending_provider_wait)
                if err:
                    write_log(f"Provider wait post failed: {err}. Will retry on next loop.")
                    time.sleep(5)
                    continue
                else:
                    write_log(f"Provider wait posted successfully: {res}")
                    if current_wait_state_file.exists():
                        os.remove(current_wait_state_file)
                    if current_task_state_file.exists():
                        os.remove(current_task_state_file)
                    pending_provider_wait = None
                    task = None
                    continue

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
