import json, time, os, sys, shutil, subprocess, uuid, traceback, signal
from pathlib import Path
import urllib.request
import urllib.error
import urllib.parse

# Paths
BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
STATE_DIR = BASE_DIR / "state"
LOGS_DIR = BASE_DIR / "logs"

# ── Ensure dirs exist ──
STATE_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ── Helpers ──

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
        return None, f"HTTP Error {e.code}: {err_msg}"
    except Exception as e:
        return None, str(e)

def write_json_atomic(path, data):
    tmp_path = path.with_suffix(".tmp")
    with open(tmp_path, "w") as f:
        json.dump(data, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)

def read_json_strict(path):
    if not path.exists():
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        write_log(f"CRITICAL: Corrupt state file {path}: {e}")
        sys.exit(1)

# ── Process group cleanup ──

def kill_process_group(pgid):
    """Kill an exact process group: SIGTERM → bounded grace → SIGKILL → verify."""
    try:
        os.killpg(pgid, 0)  # probe: is anything alive?
    except OSError:
        return True  # already dead

    write_log(f"Sending SIGTERM to process group {pgid}")
    try:
        os.killpg(pgid, signal.SIGTERM)
    except OSError:
        return True

    # Bounded 5-second grace period
    for _ in range(10):
        time.sleep(0.5)
        try:
            os.killpg(pgid, 0)
        except OSError:
            write_log(f"Process group {pgid} exited gracefully.")
            return True

    write_log(f"Process group {pgid} still alive after grace period, sending SIGKILL")
    try:
        os.killpg(pgid, signal.SIGKILL)
    except OSError:
        pass

    time.sleep(1)
    try:
        os.killpg(pgid, 0)
        write_log(f"WARNING: Process group {pgid} survived SIGKILL (D-state?).")
        return False
    except OSError:
        write_log(f"Process group {pgid} eradicated after SIGKILL.")
        return True

def pgid_is_alive(pgid):
    """Check if any process in a process group is alive."""
    if pgid is None:
        return False
    try:
        os.killpg(pgid, 0)
        return True
    except OSError:
        return False

# ── Task execution ──

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
        
    # Safe bounded execution — every subprocess has a finite timeout, no shell=True
    try:
        if action == "echo":
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
                # No shell=True: echo is invoked as an argv list, shell metacharacters are inert
                result = subprocess.run(["echo", text_to_echo], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
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
            result = subprocess.run(["git", "status"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
        else:
            return {"status": "FAILED", "stderr": f"Action '{action}' is allowed but handler is not implemented yet.", "execution_mode": "NATIVE"}
            
        return {
            "status": "SUCCESS" if result.returncode == 0 else "FAILED",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
            "execution_mode": "NATIVE"
        }
    except subprocess.TimeoutExpired:
        return {"status": "FAILED", "stderr": "Native command timed out.", "execution_mode": "NATIVE"}
    except Exception as e:
        return {"status": "FAILED", "stderr": str(e), "execution_mode": "NATIVE"}

def run_agy(task, config, current_task_state_file):
    """Launch an AGY task in its own process group.
    
    Returns (result_dict, pgid) — caller uses pgid for cleanup verification.
    """
    write_log(f"Running AI task {task['task_id']} via agy")
    instruction = task.get('instruction', task.get('description', ''))
    
    prompt = (
        f"Task ID: {task['task_id']}\nInstruction: {instruction}\n\n"
        f"You are a headless worker on Mac. You MUST execute the instruction. "
        f"After you have successfully executed the instruction, you MUST output a final JSON object "
        f"in a markdown codeblock. The JSON must contain a 'status' field set to 'SUCCESS' and a "
        f"'stdout_summary' field explaining what you did. IMPORTANT: Your current working directory "
        f"is {os.getcwd()}. Any file artifacts you create MUST be relative to this directory."
    )
    agy_bin = shutil.which("agy") or shutil.which("agy", path=os.environ.get("PATH", "") + ":/Users/user/.local/bin:/usr/local/bin:/opt/homebrew/bin")
    if not agy_bin:
        return {"status": "FAILED", "reason": "AGY_NOT_FOUND", "execution_mode": "ANTIGRAVITY"}, None
        
    wrapper = os.path.join(os.path.dirname(__file__), "limit_wrapper.sh")
    cmd = [wrapper, agy_bin, "-p", prompt, "--dangerously-skip-permissions"]
    
    try:
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, start_new_session=True
        )
        pgid = os.getpgid(process.pid)
        
        # Persist exact ownership identity before execution proceeds
        task["root_pid"] = process.pid
        task["process_group_id"] = pgid
        task["started_at"] = time.time()
        write_json_atomic(current_task_state_file, task)
        write_log(f"Task {task['task_id']}: root_pid={process.pid}, pgid={pgid}")
        
        try:
            stdout, stderr = process.communicate(timeout=300)
        except subprocess.TimeoutExpired:
            write_log(f"TimeoutExpired for task {task['task_id']}, cleaning up process group {pgid}...")
            
            # Kill stdout/stderr pipes so communicate doesn't block
            process.kill()
            stdout, stderr = process.communicate(timeout=15)
            
            # Now kill the entire owned process group
            kill_process_group(pgid)
            
            return {
                "status": "FAILED",
                "stderr": "Execution timed out and process tree was cleaned up.",
                "execution_mode": "ANTIGRAVITY"
            }, pgid
            
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
            res_json["raw_diagnostic"] = out_clean[:2000]
            
        return res_json, pgid
        
    except Exception as e:
        return {"status": "FAILED", "stderr": str(e), "execution_mode": "ANTIGRAVITY"}, None

# ── Main loop ──

def loop():
    write_log("Starting Mac Worker HTTP Daemon...")
    config = load_config()
    current_task_state_file = STATE_DIR / "current_task.json"
    result_state_file = STATE_DIR / "current_result.json"
    
    # Track the active process group for gating
    active_pgid = None
    
    # ── Resume check: pending result from previous run ──
    pending_result = read_json_strict(result_state_file)
    if pending_result:
        write_log("Found un-ACKed result from previous run, will resume posting.")
    
    # ── Resume check: unfinished task from previous run ──
    task = read_json_strict(current_task_state_file)
    if task and not pending_result:
        write_log(f"Found unfinished task {task.get('task_id')} from previous run.")
        
        # Kill orphaned process group if one was persisted
        old_pgid = task.get("process_group_id")
        if old_pgid:
            write_log(f"Cleaning up orphaned process group {old_pgid}...")
            kill_process_group(old_pgid)
        
        # Cannot safely resume — mark as FAILED, create result for posting
        write_log("Marking unfinished task as FAILED due to worker restart.")
        pending_result = {
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
        write_json_atomic(result_state_file, pending_result)
    elif task and pending_result:
        # Task finished, result exists but was never ACKed — will be posted below
        write_log(f"Resuming un-ACKed result for task {task.get('task_id')} (effect will NOT be re-executed).")
            
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
                    time.sleep(5)
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
                # ── GATE: verify previous process group is dead before claiming ──
                if pgid_is_alive(active_pgid):
                    write_log(f"Previous process group {active_pgid} still alive. Waiting for cleanup.")
                    kill_process_group(active_pgid)
                    time.sleep(2)
                    continue
                active_pgid = None

                # ── GATE: resource pressure check ──
                try:
                    import resource_guard
                    safety = resource_guard.enforce_resource_safety()
                    if safety["throttled"]:
                        write_log("Local resource pressure is high. Throttling new work.")
                        time.sleep(5)
                        continue
                except Exception as e:
                    write_log(f"Resource guard error (non-fatal): {e}")
                    
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
                    mode = "NATIVE"

                task_pgid = None
                if mode == "NATIVE":
                    result = run_native(task, config)
                else:
                    result, task_pgid = run_agy(task, config, current_task_state_file)
                
                # ── Post-execution: ensure owned tree is dead ──
                if task_pgid is not None:
                    if pgid_is_alive(task_pgid):
                        write_log(f"Post-execution: process group {task_pgid} still alive, cleaning up...")
                        kill_process_group(task_pgid)
                    active_pgid = task_pgid  # remember for pre-claim gate
                
                # Format result payload
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
                
                # Persist result BEFORE attempting to post — crash-safe
                write_json_atomic(result_state_file, payload)
            
            if payload:
                # Try to post result; if server is down, preserve state and retry next loop
                res, err = http_post(config, "/tasks/result", payload)
                if err:
                    write_log(f"Result post failed: {err}. State preserved, will retry.")
                    # Do NOT clear task or result state. Do NOT claim new task.
                    # pending_result stays set so next iteration retries.
                    pending_result = payload
                else:
                    write_log(f"Result posted successfully: {res}")
                    # ACK received — NOW it is safe to clear local state
                    if current_task_state_file.exists():
                        os.remove(current_task_state_file)
                    if result_state_file.exists():
                        os.remove(result_state_file)
                    task = None
                    pending_result = None
                
        except Exception as e:
            write_log(f"Error in HTTP poll loop: {e}\n{traceback.format_exc()}")
            
        time.sleep(config.get("POLL_INTERVAL_SECONDS", 5))

if __name__ == "__main__":
    loop()
