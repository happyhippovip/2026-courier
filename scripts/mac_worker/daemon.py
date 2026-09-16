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
    log_file = LOGS_DIR / "worker.log"
    if log_file.exists() and log_file.stat().st_size > 1024 * 1024:
        backup = LOGS_DIR / "worker.log.1"
        if backup.exists():
            backup.unlink()
        log_file.rename(backup)
    with open(log_file, "a") as f:
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
        return None, {"status": e.code, "message": err_msg}
    except Exception as e:
        return None, {"status": 500, "message": str(e)}

def http_get(config, endpoint):
    url = config["COURIER_SERVER"].rstrip("/") + endpoint
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {config.get('COURIER_API_KEY', '')}")
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        return None, {"status": e.code, "message": err_msg}
    except Exception as e:
        return None, {"status": 500, "message": str(e)}

def write_json_atomic(path, data):
    tmp_path = path.with_suffix(".tmp")
    with open(tmp_path, "w") as f:
        json.dump(data, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)

def read_json_strict(path):
    if not path.exists(): return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        write_log(f"CRITICAL: Corrupt state file {path}: {e}")
        sys.exit(1)

def run_native(task, config):
    write_log(f"Running NATIVE task {task['task_id']}")
    instruction = task.get('instruction', task.get('description', ''))
    
    # ALLOWLIST CHECK
    action = task.get("action", "").lower()
    allowed_actions = ["create_file", "read_file_metadata", "git_status", "run_known_test", "hash_file", "echo", "ssh"]
    
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
            import shlex
            text_to_echo = instruction
            filename = None
            if " to " in instruction.lower():
                parts = instruction.lower().split(" to ", 1)
                text_to_echo = instruction[:len(parts[0])].replace("Echo", "").replace("echo", "").strip()
                filename = instruction[len(parts[0])+4:].split()[0].strip()
            
            if filename:
                with open(filename, "w") as f:
                    f.write(text_to_echo + "\n")
                return {"status": "SUCCESS", "stdout": f"Echoed to {filename}", "execution_mode": "NATIVE"}
            else:
                result = subprocess.run(["echo", text_to_echo], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
                return {"status": "SUCCESS" if result.returncode == 0 else "FAILED", "stdout": result.stdout, "stderr": result.stderr, "execution_mode": "NATIVE"}
        elif action == "create_file":
            filename = task.get("file_path", instruction.split()[0] if instruction else "")
            content = task.get("content", task.get("description", ""))
            try:
                with open(filename, "w") as f:
                    f.write(content)
                return {"status": "SUCCESS", "stdout": f"Created {filename}", "execution_mode": "NATIVE"}
            except Exception as e:
                return {"status": "FAILED", "stderr": str(e), "execution_mode": "NATIVE"}
        elif action == "ssh":
            cmd = ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no"] + instruction.split()
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if proc.returncode == 0:
                    return {"status": "SUCCESS", "stdout": proc.stdout, "execution_mode": "NATIVE"}
                else:
                    return {"status": "FAILED", "stderr": proc.stderr, "execution_mode": "NATIVE"}
            except subprocess.TimeoutExpired:
                return {"status": "FAILED", "stderr": "SSH Timeout", "execution_mode": "NATIVE"}
        elif action == "git_status":
            result = subprocess.run(["git", "status"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
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

def run_agy(task, config, current_task_state_file=None):
    write_log(f"Running AI task {task['task_id']} via agy")
    instruction = task.get('instruction', task.get('description', ''))
    
    prompt = f"Task ID: {task['task_id']}\nInstruction: {instruction}\n\nYou are a headless worker on Mac.\nCONTEXT RULES:\n- Perform targeted reads only. Do NOT perform full-repo scans by default.\n- Operate ONLY on admitted files or your exact TaskPacket scope. Broader scope requires explicit admission.\n- Keep logs bounded. Do NOT replay transcripts or re-download unchanged files.\n\nYou MUST execute the instruction. After you have successfully executed the instruction, you MUST output a final JSON object in a markdown codeblock. The JSON must contain a 'status' field set to 'SUCCESS' and a 'stdout_summary' field explaining what you did. IMPORTANT: Your current working directory is {os.getcwd()}. Any file artifacts you create MUST be relative to this directory."
    agy_bin = shutil.which("agy") or shutil.which("agy", path=os.environ.get("PATH", "") + ":/Users/user/.local/bin:/usr/local/bin:/opt/homebrew/bin")
    if not agy_bin:
        return {"status": "FAILED", "reason": "AGY_NOT_FOUND", "execution_mode": "ANTIGRAVITY"}
        
    wrapper = os.path.join(os.path.dirname(__file__), "limit_wrapper.sh")
    model = task.get("model", "flash")
    cmd = [wrapper, agy_bin, "--model", model, "-p", prompt, "--dangerously-skip-permissions"]
    
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        if current_task_state_file:
            task["root_pid"] = process.pid
            task["process_group_id"] = os.getpgid(process.pid)
            task["started_at"] = time.time()
            write_json_atomic(current_task_state_file, task)
        try:
            stdout, stderr = process.communicate(timeout=300)
        except subprocess.TimeoutExpired:
            import signal
            write_log(f"TimeoutExpired for task {task['task_id']}, marking cleanup pending and terminating process group {process.pid}...")
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except OSError:
                pass
            
            try:
                process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                write_log(f"Process group {process.pid} did not exit gracefully, sending SIGKILL...")
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except OSError:
                    pass
                process.communicate() # Reap
                
            # Verify the process group is truly gone
            try:
                os.killpg(process.pid, 0)
                write_log(f"CRITICAL: Process group {process.pid} still exists after SIGKILL! It might be a zombie or stuck in D state.")
            except OSError:
                write_log(f"Process group {process.pid} successfully eradicated.")
                
            return {"status": "FAILED", "stderr": "Execution timed out and process tree was cleaned up.", "execution_mode": "ANTIGRAVITY"}
            
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
            
        # Classify provider/account interruptions
        combined_output = (stdout + "\n" + stderr).lower()
        if any(term in combined_output for term in ["quota reached", "individual quota reached", "rate limit", "provider unavailable", "account limit", "session limit", "429 too many requests", "resource exhausted"]):
            res_json["status"] = "WAITING_PROVIDER"
        elif any(term in combined_output for term in ["temporary failure", "internal server error", "503 service unavailable", "502 bad gateway", "504 gateway timeout"]):
            res_json["status"] = "BLOCKED_TRANSIENT"
            
        return res_json
        
    except Exception as e:
        return {"status": "FAILED", "stderr": str(e), "execution_mode": "ANTIGRAVITY"}

def loop():
    write_log("Starting Mac Worker HTTP Daemon...")
    config = load_config()
    current_task_state_file = STATE_DIR / "current_task.json"
    result_state_file = STATE_DIR / "current_result.json"
    
    # Check for pending result
    pending_result = None
    pending_result = read_json_strict(result_state_file)
    if pending_result:
        write_log("Found un-ACKed result from previous run, resuming post...")
            
    task = read_json_strict(current_task_state_file)
    if task and not pending_result:
        write_log("Found unfinished task from previous run, checking for orphans...")
        if "process_group_id" in task:
            pgid = task["process_group_id"]
            import signal
            try:
                os.killpg(pgid, 0)
                write_log(f"Found orphaned process group {pgid}, cleaning up...")
                os.killpg(pgid, signal.SIGTERM)
                time.sleep(2)
                try:
                    os.killpg(pgid, signal.SIGKILL)
                except OSError:
                    pass
            except OSError:
                write_log(f"Process group {pgid} already dead.")
        
        # We cannot safely resume a half-executed AI task without duplication risk
        # We should just mark it as FAILED (Ambiguous)
        write_log("Marking unfinished task as FAILED due to worker restart.")
        payload = {
            "worker_id": config["WORKER_ID"],
            "goal_id": task.get("goal_id"),
            "task_id": task["task_id"],
            "dispatch_id": task.get("dispatch_id"),
            "attempt_id": task.get("attempt_id"),
            "run_id": str(uuid.uuid4()),
            "result_id": str(uuid.uuid4()),
            "status": "FAILED",
            "artifacts": [],
            "provider": "mac_antigravity",
            "raw_result": {"status": "FAILED", "stderr": "Worker crashed/restarted during execution."}
        }
        write_json_atomic(result_state_file, payload)
        pending_result = payload

            
    registered = False
    
    while True:
        try:
            if not registered:
                reg_payload = {
                    "worker_id": config["WORKER_ID"],
                    "platform": "macos",
                    "capabilities": ["macos", "linux", "antigravity"],
                    "cost_class": "high"
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
                # Enforce resource safety before claiming
                import resource_guard
                try:
                    safety = resource_guard.enforce_resource_safety()
                    if safety["throttled"]:
                        write_log("Local resource pressure is high. Throttling new work.")
                        time.sleep(5)
                        continue
                except Exception as e:
                    write_log(f"Resource guard error: {e}")
                    
                # Claim Task
                res, err = http_post(config, "/tasks/claim", {"worker_id": config["WORKER_ID"]})
                if err:
                    write_log(f"Claim failed: {err}")
                    time.sleep(5)
                    continue
                    
                task = res.get("task")
                if task:
                    write_json_atomic(current_task_state_file, task)
                        
            payload = None
            if pending_result:
                payload = pending_result
            elif task:
                write_log(f"Processing task {task['task_id']}")
                mode = task.get("mode", "ANTIGRAVITY")
                # Fallback to NATIVE if requested via target_agent routing
                target = task.get("target_agent", "").lower()
                if "mac" in target and mode == "ANTIGRAVITY" and task.get("action") in ["echo", "git_status", "create_file", "ssh"]:
                    # For simple testing/canary routing we force NATIVE if action is allowed
                    mode = "NATIVE"

                if mode == "NATIVE":
                    result = run_native(task, config)
                else:
                    result = run_agy(task, config, current_task_state_file)
                
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
                
                # Persist the result so it can be resumed after restart
                result_state_file = STATE_DIR / "current_result.json"
                write_json_atomic(result_state_file, payload)
            
            if payload:
                # Bounded retry until successful POST
                retries = 0
                success = False
                while retries < 3:
                    res, err = http_post(config, "/tasks/result", payload)
                    if err:
                        if isinstance(err, dict) and err.get("status") in [404, 409]:
                            write_log(f"Server rejected result with {err['status']}, likely a STALE_UI_HANDLE. Dropping task.")
                            if current_task_state_file.exists(): os.remove(current_task_state_file)
                            if result_state_file.exists(): os.remove(result_state_file)
                            task = None
                            pending_result = None
                            success = True
                            break
                        write_log(f"Result post failed: {err}. Retrying in 10s...")
                        time.sleep(10)
                        retries += 1
                    else:
                        write_log(f"Result posted successfully: {res}")
                        
                        # Wait for verification and then cleanup exactly the task-owned transient processes
                        if task and "process_group_id" in task:
                            write_log("Waiting for task lifecycle to terminate before releasing transient processes...")
                            terminal = False
                            while not terminal:
                                t_res, t_err = http_get(config, f"/tasks/{task['task_id']}")
                                if t_err:
                                    if isinstance(t_err, dict) and t_err.get("status") in [404, 409]:
                                        write_log("Task no longer exists on server (STALE_UI_HANDLE). Terminating polling.")
                                        terminal = True
                                    else:
                                        time.sleep(5)
                                    continue
                                t_status = t_res.get("status")
                                if t_status in ["RECONCILED", "FAILED_VERIFICATION", "FAILED_TERMINAL", "QUEUED", "HUMAN_REQUIRED", "WAITING_PROVIDER", "BLOCKED_TRANSIENT"]:
                                    terminal = True
                                else:
                                    time.sleep(5)
                                    
                            pgid = task["process_group_id"]
                            import signal
                            try:
                                os.killpg(pgid, 0)
                                write_log(f"Cleaning up exact transient process group {pgid} after terminal state...")
                                os.killpg(pgid, signal.SIGTERM)
                                time.sleep(2)
                                try:
                                    os.killpg(pgid, signal.SIGKILL)
                                except OSError:
                                    pass
                            except OSError:
                                pass
                                
                        if current_task_state_file.exists():
                            os.remove(current_task_state_file)
                        if result_state_file.exists():
                            os.remove(result_state_file)
                        task = None
                        pending_result = None
                        success = True
                        break
                
                if not success:
                    write_log("Result post exhausted retries. Halting task processing to preserve state.")
                    time.sleep(30)
                    continue
                
        except Exception as e:
            write_log(f"Error in HTTP poll loop: {e}\n{traceback.format_exc()}")
            
        time.sleep(config.get("POLL_INTERVAL_SECONDS", 5))

if __name__ == "__main__":
    loop()
