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
    # S04: Bounded logs
    if log_file.exists() and log_file.stat().st_size > 5 * 1024 * 1024:
        try:
            with open(log_file, "r") as f:
                content = f.read()
            with open(log_file, "w") as f:
                f.write(content[-2 * 1024 * 1024:]) # Keep last 2MB
        except Exception:
            pass
    with open(log_file, "a") as f:
        import time
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
    import signal, os, subprocess, json
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
    pid_file = STATE_DIR / "current_task_pid.json"
    process = None
    try:
        if action == "echo":
            process = subprocess.Popen(instruction, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, executable="/bin/bash", preexec_fn=os.setsid)
        elif action == "git_status":
            process = subprocess.Popen(["git", "status"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, preexec_fn=os.setsid)
        else:
            return {"status": "FAILED", "stderr": f"Action '{action}' is allowed but handler is not implemented yet.", "execution_mode": "NATIVE"}
            
        with open(pid_file, "w") as f:
            json.dump({"pid": process.pid, "pgid": os.getpgid(process.pid)}, f)
            
        stdout, stderr = process.communicate(timeout=300)
        
        if pid_file.exists():
            os.remove(pid_file)
            
        return {
            "status": "SUCCESS" if process.returncode == 0 else "FAILED",
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": process.returncode,
            "execution_mode": "NATIVE"
        }
    except subprocess.TimeoutExpired as e:
        write_log(f"Task {task['task_id']} timed out. Cleaning up exact process group.")
        if process:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except:
                pass
        if pid_file.exists():
            os.remove(pid_file)
        return {"status": "FAILED", "stderr": "TimeoutExpired - Process killed.", "execution_mode": "NATIVE"}
    except Exception as e:
        if process:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except:
                pass
        if pid_file.exists():
            os.remove(pid_file)
        return {"status": "FAILED", "stderr": str(e), "execution_mode": "NATIVE"}

def run_agy(task, config):
    import signal
    write_log(f"Running AI task {task['task_id']} via agy")
    instruction = task.get('instruction', task.get('description', ''))
    
    prompt = f"""Task ID: {task['task_id']}
Instruction: {instruction}

You are a headless worker on Mac. You MUST execute the instruction. 
RULES: MAX_HEAVY_LOCAL_EXECUTIONS=1, MAX_ACTIVE_SUBAGENTS=2, TIMER_DEFAULT=NO. Do NOT use broad killall or unlimited retries.
After you have successfully executed the instruction, you MUST output a final JSON object in a markdown codeblock. The JSON must contain a 'status' field set to 'SUCCESS' and a 'stdout_summary' field explaining what you did. IMPORTANT: Your current working directory is {os.getcwd()}. Any file artifacts you create MUST be relative to this directory."""
    agy_bin = shutil.which("agy") or shutil.which("agy", path=os.environ.get("PATH", "") + ":/Users/user/.local/bin:/usr/local/bin:/opt/homebrew/bin")
    if not agy_bin:
        return {"status": "FAILED", "reason": "AGY_NOT_FOUND", "execution_mode": "ANTIGRAVITY"}
        
    wrapper = os.path.join(os.path.dirname(__file__), "limit_wrapper.sh")
    cmd = [wrapper, agy_bin, "-p", prompt, "--dangerously-skip-permissions"]
    
    pid_file = STATE_DIR / "current_task_pid.json"
    process = None
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, preexec_fn=os.setsid)
        
        with open(pid_file, "w") as f:
            json.dump({"pid": process.pid, "pgid": os.getpgid(process.pid)}, f)
            
        stdout, stderr = process.communicate(timeout=300)
        
        if pid_file.exists():
            os.remove(pid_file)
            
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
        
    except subprocess.TimeoutExpired as e:
        write_log(f"Task {task['task_id']} timed out (stale session). Cleaning up exact process group.")
        if process:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except:
                pass
        if pid_file.exists():
            os.remove(pid_file)
        return {"status": "FAILED", "stderr": "TimeoutExpired - Process killed.", "execution_mode": "ANTIGRAVITY"}
    except Exception as e:
        if process:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except:
                pass
        if pid_file.exists():
            os.remove(pid_file)
        return {"status": "FAILED", "stderr": str(e), "execution_mode": "ANTIGRAVITY"}


import fcntl
def acquire_single_instance_lock():
    lock_file = STATE_DIR / "daemon.lock"
    lock_fd = open(lock_file, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_fd
    except BlockingIOError:
        print("Another instance of daemon is already running. Exiting.")
        sys.exit(0)

def loop():
    _lock_fd = acquire_single_instance_lock()

    write_log("Starting Mac Worker HTTP Daemon...")
    config = load_config()
    current_task_state_file = STATE_DIR / "current_task.json"
    current_result_file = STATE_DIR / "current_result.json"
    # Cleanup any stale process from a previous run/crash
    pid_file = STATE_DIR / "current_task_pid.json"
    if pid_file.exists():
        try:
            import signal
            with open(pid_file, "r") as f:
                pdata = json.load(f)
            pgid = pdata.get("pgid")
            if pgid:
                write_log(f"Found stale execution pgid {pgid}. Killing to release session.")
                os.killpg(pgid, signal.SIGKILL)
        except Exception as e:
            write_log(f"Error cleaning up stale pid: {e}")
        try:
            os.remove(pid_file)
        except:
            pass

    
    # S02 Crash loop breaker
    task_crash_file = STATE_DIR / "task_crash_count.json"
    crash_counts = {}
    if task_crash_file.exists():
        try:
            with open(task_crash_file, "r") as f:
                crash_counts = json.load(f)
        except:
            pass

    # Load previously claimed task for duplicate protection
    task = None
    if current_task_state_file.exists():
        write_log("Found unfinished task from previous run, resuming...")

        if current_result_file.exists():
            with open(current_result_file, 'r') as f:
                saved = json.load(f)
            write_log("Recovered unsent durable result from disk.")
            
            # Post loop right here
            import random
            post_backoff = 2
            while True:
                res, err = http_post(config, "/tasks/result", saved["payload"])
                if err:
                    write_log(f"Result post failed: {err}. Retrying in {post_backoff}s...")
                    time.sleep(post_backoff + random.uniform(0, 2))
                    post_backoff = min(60, post_backoff * 2)
                else:
                    write_log(f"Result posted successfully: {res}")
                    break
                    
            os.remove(current_result_file)
            if current_task_state_file.exists():
                os.remove(current_task_state_file)
            task = None
        elif current_task_state_file.exists():
            with open(current_task_state_file, 'r') as f:
                task = json.load(f)

            
        # Increment crash count
        tid = task.get("task_id", "unknown")
        c_count = crash_counts.get(tid, 0) + 1
        crash_counts[tid] = c_count
        with open(str(task_crash_file) + ".tmp", "w") as f:
            json.dump(crash_counts, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(str(task_crash_file) + ".tmp", task_crash_file)
            
        if c_count > 2:
            write_log(f"Task {tid} has crashed {c_count} times. Breaking circuit and returning FAILED.")
            # Post failed result
            payload = {
                "worker_id": config["WORKER_ID"],
                "goal_id": task.get("goal_id"),
                "task_id": tid,
                "dispatch_id": task.get("dispatch_id"),
                "attempt_id": task.get("attempt_id"),
                "run_id": str(uuid.uuid4()),
                "result_id": str(uuid.uuid4()),
                "status": "FAILED",
                "stderr": f"S02 Circuit Breaker: Task crashed {c_count} times.",
                "execution_mode": "CIRCUIT_BREAKER",
                "artifacts": [],
                "raw_result": {"status": "FAILED", "reason": "CRASH_LOOP"}
            }
            http_post(config, "/tasks/result", payload)
            if current_task_state_file.exists():
                os.remove(current_task_state_file)
            task = None
            
    registered = False
    error_backoff = 2
    
    while True:
        try:
            if not registered:
                reg_payload = {
                    "worker_id": config["WORKER_ID"],
                    "platform": "macos",
                    "capabilities": ["macos", "antigravity"]
                }
                res, err = http_post(config, "/workers/register", reg_payload)
                if err:
                    write_log(f"Failed to register: {err}")
                    time.sleep(error_backoff + __import__("random").uniform(0, 2))
                    error_backoff = min(60, error_backoff * 2)
                    continue
                write_log("Registered successfully.")
                registered = True
            # Cleanup old temp dirs
            try:
                import shutil
                paths = [p for p in STATE_DIR.iterdir() if p.is_dir() and p.name.startswith("task_")]
                paths.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                for p in paths[5:]: # Keep last 5
                    shutil.rmtree(p)
            except Exception:
                pass

                error_backoff = 2
                
            # Heartbeat
            # Resource / Heat protection
            load1, load5, load15 = os.getloadavg()
            is_hot = load1 > 8.0  # Simple threshold for max local executions/pressure
            payload_hb = {"worker_id": config["WORKER_ID"]}
            if is_hot:
                write_log(f"System is hot (load {load1:.2f}). Pausing claims.")
                payload_hb["available"] = False

            res, err = http_post(config, "/workers/heartbeat", payload_hb)
            if err:
                write_log(f"Heartbeat failed: {err}")
                registered = False
                time.sleep(error_backoff + __import__("random").uniform(0, 2))
                error_backoff = min(60, error_backoff * 2)
                continue
                
            if not task:
                # Claim Task
                res, err = http_post(config, "/tasks/claim", {"worker_id": config["WORKER_ID"]})
                if err:
                    write_log(f"Claim failed: {err}")
                    time.sleep(error_backoff + __import__("random").uniform(0, 2))
                    error_backoff = min(60, error_backoff * 2)
                    continue
                    
                task = res.get("task")
                error_backoff = 2
                if task:
                    temp_task_file = str(current_task_state_file) + ".tmp"
                    with open(temp_task_file, 'w') as f:
                        json.dump(task, f)
                        f.flush()
                        os.fsync(f.fileno())
                    os.replace(temp_task_file, current_task_state_file)
                        
            if task:
                write_log(f"Processing task {task['task_id']}")
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
                
                # S08/S05: Save current_result before attempting network post
                temp_res = str(current_result_file) + ".tmp"
                with open(temp_res, 'w') as f:
                    json.dump({"task": task, "payload": payload}, f)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temp_res, current_result_file)
                
                # Infinite backoff loop for posting result (S05: no lost tasks, low-load waiting)
                import random
                post_backoff = 2
                while True:
                    res, err = http_post(config, "/tasks/result", payload)
                    if err:
                        write_log(f"Result post failed: {err}. Retrying in {post_backoff}s...")
                        time.sleep(post_backoff + random.uniform(0, 2))
                        post_backoff = min(60, post_backoff * 2)
                    else:
                        write_log(f"Result posted successfully: {res}")
                        break
                        
                if current_result_file.exists():
                    os.remove(current_result_file)
                
                if current_task_state_file.exists():
                    os.remove(current_task_state_file)
                    
                # Clear crash count
                tid = task.get("task_id")
                if tid in crash_counts:
                    del crash_counts[tid]
                    with open(str(task_crash_file) + ".tmp", "w") as f:
                        json.dump(crash_counts, f)
                        f.flush()
                        os.fsync(f.fileno())
                    os.replace(str(task_crash_file) + ".tmp", task_crash_file)
                    
                task = None
                
        except Exception as e:
            write_log(f"Error in HTTP poll loop: {e}\n{traceback.format_exc()}")
            
        time.sleep(config.get("POLL_INTERVAL_SECONDS", 5))

if __name__ == "__main__":
    loop()
