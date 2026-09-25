import json, time, os, sys, shutil, subprocess, uuid, traceback
from pathlib import Path
import urllib.request
import urllib.error
import urllib.parse
import signal

# Track active process groups for cleanup on shutdown
ACTIVE_PGIDS = set()

def sigterm_handler(signum, frame):
    for pgid in list(ACTIVE_PGIDS):
        try:
            if hasattr(os, "killpg"):
                os.killpg(pgid, signal.SIGKILL)
            else:
                import psutil
                parent = psutil.Process(pgid)
                for child in parent.children(recursive=True):
                    child.kill()
                parent.kill()
        except Exception:
            pass
    sys.exit(0)

signal.signal(signal.SIGTERM, sigterm_handler)
signal.signal(signal.SIGINT, sigterm_handler)

# Paths
BASE_DIR = Path(__file__).parent
CONFIG_PATH = Path(os.environ.get("COURIER_CONFIG_PATH") or (BASE_DIR / "config.json"))
STATE_DIR = Path(os.environ.get("COURIER_WORKER_STATE_DIR") or (BASE_DIR / "state"))
LOGS_DIR = Path(os.environ.get("COURIER_WORKER_LOGS_DIR") or (BASE_DIR / "logs"))
LOGS_DIR.mkdir(parents=True, exist_ok=True)
STATE_DIR.mkdir(parents=True, exist_ok=True)
SECRET_KEY = None


import sqlite3
import threading

def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)
    else:
        config = {}
        
    if config.get("WORKER_ID") in ["test-mac", "", None]:
        import socket, uuid
        config["WORKER_ID"] = f"MAC-{socket.gethostname().split('.')[0].upper()}-{uuid.uuid4().hex[:6].upper()}"
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "w") as f:
                json.dump(config, f)

    
    # Try reading from macOS keychain
    try:
        pass # Bypass keychain to fix 401
    except (Exception):
        pass
        
    try:
        srv = subprocess.check_output(["security", "find-generic-password", "-a", "courier_worker", "-s", "courier_server_url", "-w"], stderr=subprocess.DEVNULL)
        config["COURIER_SERVER"] = srv.decode("utf-8").strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    # Environment overrides
    if "COURIER_SERVER" in os.environ:
        config["COURIER_SERVER"] = os.environ["COURIER_SERVER"]
    if "COURIER_API_KEY" in os.environ:
        config["COURIER_API_KEY"] = os.environ["COURIER_API_KEY"]
    if "COURIER_WORKER_ID" in os.environ:
        config["WORKER_ID"] = os.environ["COURIER_WORKER_ID"]
    if "POLL_INTERVAL_SECONDS" in os.environ:
        config["POLL_INTERVAL_SECONDS"] = float(os.environ["POLL_INTERVAL_SECONDS"])
    if "IDLE_POLL_INTERVAL_SECONDS" in os.environ:
        config["IDLE_POLL_INTERVAL_SECONDS"] = float(os.environ["IDLE_POLL_INTERVAL_SECONDS"])
    if not config.get('COURIER_API_KEY'):
        import sys; sys.stderr.write('FATAL: Missing credentials fail closed.\n'); sys.exit(1)
    
    # Strip any whitespace/newlines from the key to avoid HTTP header corruption
    config['COURIER_API_KEY'] = str(config['COURIER_API_KEY']).strip()
    
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
    allowed_actions = ["git_status", "echo", "touch", "sleep"]
    
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
            
            # Support basic echo > file
            if ">" in args:
                idx = args.index(">")
                if idx + 1 < len(args):
                    file_path = args[idx+1]
                    # basic safety for path
                    if ".." in file_path or "/" in file_path or "\\" in file_path:
                        return {"status": "FAILED", "stderr": "Invalid path for redirect.", "execution_mode": "NATIVE"}
                    content = " ".join(args[1:idx])
                    try:
                        with open(file_path, "w") as f:
                            f.write(content + "\n")
                        return {
                            "status": "SUCCESS",
                            "stdout": "",
                            "stderr": "",
                            "exit_code": 0,
                            "execution_mode": "NATIVE"
                        }
                    except Exception as e:
                        return {"status": "FAILED", "stderr": str(e), "execution_mode": "NATIVE"}
            
            # Ban shell-injection-like input and path escape patterns
            for arg in args:
                if any(bad in arg for bad in [';', '|', '&', '>', '<', '$', '..', '`']):
                    return {"status": "FAILED", "stderr": "Shell operators and path escapes are banned.", "execution_mode": "NATIVE"}

            result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=False)

            
        elif action == "sleep":
            args = instruction.split()
            if not args or args[0].lower() != "sleep":
                return {"status": "FAILED", "stderr": "Malformed sleep command.", "execution_mode": "NATIVE"}
            import time
            time.sleep(float(args[1]))
            class DummyResult: pass
            result = DummyResult()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
            
        elif action == "touch":
            args = instruction.split()
            if not args or args[0].lower() != "touch":
                return {"status": "FAILED", "stderr": "Malformed touch command.", "execution_mode": "NATIVE"}
            file_name = args[1]
            if any(bad in file_name for bad in ['/', '\\', '..', ';', '&']):
                return {"status": "FAILED", "stderr": "Invalid path for touch.", "execution_mode": "NATIVE"}
            
            with open(file_name, "w") as f:
                f.write("canary")
            class DummyResult: pass
            result = DummyResult()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
            
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
    if os.name == "nt":
        cmd = [agy_bin, "-p", prompt, "--dangerously-skip-permissions"]
    else:
        cmd = [wrapper, agy_bin, "-p", prompt, "--dangerously-skip-permissions"]
    
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        if hasattr(os, "getpgid"):
            pgid = os.getpgid(process.pid)
            ACTIVE_PGIDS.add(pgid)
        else:
            ACTIVE_PGIDS.add(process.pid)
            
        try:
            stdout, stderr = process.communicate(timeout=300)
        except subprocess.TimeoutExpired:
            try:
                if hasattr(os, "killpg"):
                    os.killpg(pgid, signal.SIGTERM)
                    time.sleep(1)
                    os.killpg(pgid, signal.SIGKILL)
                else:
                    process.terminate()
                    time.sleep(1)
                    process.kill()
            except Exception:
                pass
            stdout, stderr = process.communicate()
            return {"status": "FAILED", "stderr": "Execution timed out", "execution_mode": "ANTIGRAVITY"}
        finally:
            if hasattr(os, "getpgid"):
                ACTIVE_PGIDS.discard(pgid)
            else:
                ACTIVE_PGIDS.discard(process.pid)
        
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
        
    if os.name == "nt":
        cmd = [gh_bin, "copilot", "suggest", "-t", "shell", prompt]
    else:
        cmd = [wrapper, gh_bin, "copilot", "suggest", "-t", "shell", prompt]
    
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        if hasattr(os, "getpgid"):
            pgid = os.getpgid(process.pid)
            ACTIVE_PGIDS.add(pgid)
        else:
            ACTIVE_PGIDS.add(process.pid)
            
        try:
            stdout, stderr = process.communicate(timeout=300)
        except subprocess.TimeoutExpired:
            try:
                if hasattr(os, "killpg"):
                    os.killpg(pgid, signal.SIGTERM)
                    time.sleep(1)
                    os.killpg(pgid, signal.SIGKILL)
                else:
                    process.terminate()
                    time.sleep(1)
                    process.kill()
            except Exception:
                pass
            stdout, stderr = process.communicate()
            return {"status": "FAILED", "stderr": "Execution timed out", "execution_mode": "COPILOT"}
        finally:
            if hasattr(os, "getpgid"):
                ACTIVE_PGIDS.discard(pgid)
            else:
                ACTIVE_PGIDS.discard(process.pid)
        
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




try:
    import fcntl
except ImportError:
    fcntl = None

_lock_file_handle = None

def acquire_lock(worker_id):
    global _lock_file_handle
    if fcntl is None:
        # Fallback for local dev/testing on Windows, or just return True
        return True
    
    lock_path = STATE_DIR / f'courier_worker_{worker_id}.lock'
    try:
        _lock_file_handle = open(lock_path, 'w')
        fcntl.flock(_lock_file_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except (IOError, OSError):
        return False


def get_db_path():
    db_env = os.environ.get("COURIER_MAC_DB_PATH")
    if db_env:
        p = Path(db_env)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return STATE_DIR / 'queue.db'

def init_db():
    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS inbox (
                task_id TEXT PRIMARY KEY,
                task_json TEXT NOT NULL,
                status TEXT NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS outbox (
                task_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                status TEXT NOT NULL,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

def register_worker(config):
    caps = ["macos", "linux"]
    if shutil.which("agy") or shutil.which("agy", path="/Users/user/.local/bin:/usr/local/bin:/opt/homebrew/bin"):
        caps.append("antigravity")
    if shutil.which("gh") and "copilot" in subprocess.getoutput("gh extension list"):
        caps.append("copilot")
    if "COURIER_WORKER_CAPABILITIES" in os.environ:
        caps.extend([c.strip() for c in os.environ["COURIER_WORKER_CAPABILITIES"].split(",") if c.strip()])

    reg_payload = {
        "worker_id": config["WORKER_ID"],
        "platform": "macos",
        "capabilities": list(set(caps)),
        "cost_class": os.environ.get("WORKER_COST_CLASS", config.get("cost_class", "low"))
    }
    res, err = http_post(config, "/workers/register", reg_payload)
    if err:
        write_log(f"Failed to register: {err}")
        return False
    write_log("Registered successfully.")
    return True

def heartbeat_loop(config):
    while True:
        try:
            res, err = http_post(config, "/workers/heartbeat", {"worker_id": config["WORKER_ID"]})
            if err:
                write_log(f"Heartbeat failed: {err}")
                # Try re-registering
                register_worker(config)
        except Exception:
            pass
        time.sleep(30)

def fetcher_loop(config):
    error_backoff = 10
    worker_id = config["WORKER_ID"]
    while True:
        try:
            res, err = http_post(config, "/tasks/claim", {"worker_id": worker_id})
            if err:
                write_log(f"Claim failed: {err}")
                time.sleep(error_backoff)
                error_backoff = min(300, error_backoff * 2)
                continue
            
            if res and res.get("task"):
                task = res["task"]
                task_id = task["task_id"]
                write_log(f"Claimed task {task_id}")
                with sqlite3.connect(get_db_path()) as conn:
                    conn.execute("INSERT OR IGNORE INTO inbox (task_id, task_json, status) VALUES (?, ?, ?)", (task_id, json.dumps(task), 'QUEUED'))
                    conn.commit()
                write_log(f"Task {task_id} queued in inbox.")
                error_backoff = 10
        except Exception as e:
            write_log(f"Fetcher error: {e}")
            time.sleep(error_backoff)
            error_backoff = min(300, error_backoff * 2)
            continue


def cleanup_loop(config):
    worker_id = config["WORKER_ID"]
    while True:
        try:
            with sqlite3.connect(get_db_path()) as conn:
                conn.execute("DELETE FROM outbox WHERE status = 'SENT' AND completed_at < datetime('now', '-7 days')")
                conn.execute("DELETE FROM inbox WHERE status IN ('DONE', 'QUARANTINE') AND added_at < datetime('now', '-7 days')")
        except Exception as e:
            write_log(f"Cleanup error: {e}")
        time.sleep(3600)

def sender_loop(config):
    worker_id = config["WORKER_ID"]
    while True:
        try:
            with sqlite3.connect(get_db_path()) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT task_id, payload_json, endpoint FROM outbox WHERE status = 'PENDING' ORDER BY completed_at ASC")
                rows = cursor.fetchall()
            for row in rows:
                task_id = row['task_id']
                payload = json.loads(row['payload_json'])
                endpoint = row['endpoint']
                try:
                    res, err = http_post(config, endpoint, payload)
                    if err:
                        write_log(f"Sender failed to post result for {task_id}: {err}")
                        break
                    with sqlite3.connect(get_db_path()) as conn:
                        conn.execute("UPDATE outbox SET status = 'SENT' WHERE task_id = ?", (task_id,))
                    write_log(f"Task {task_id} payload sent to {endpoint}.")
                except Exception as e:
                    write_log(f"Sender error for {task_id}: {e}")
                    break
        except Exception as e:
            write_log(f"Sender error: {e}")
        time.sleep(2.0)

def loop():
    config = load_config()
    worker_id = config["WORKER_ID"]
    write_log("Starting Mac Worker HTTP Daemon with Durable Queue...")
    
    if not acquire_lock(worker_id):
        write_log(f"FATAL: Another Mac worker instance with ID {worker_id} is already running. Exiting to prevent duplicate execution.")
        sys.exit(1)
        
    init_db()
    
    while not register_worker(config):
        time.sleep(5)
        
    threading.Thread(target=heartbeat_loop, args=(config,), daemon=True).start()
    threading.Thread(target=fetcher_loop, args=(config,), daemon=True).start()
    threading.Thread(target=sender_loop, args=(config,), daemon=True).start()
    threading.Thread(target=cleanup_loop, args=(config,), daemon=True).start()
    
    # Reconcile ambiguous crash state (VERIFY_AFTER_CRASH)
    with sqlite3.connect(get_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT task_id, task_json FROM inbox WHERE status = 'RUNNING'")
        crashed_tasks = cursor.fetchall()
        for row in crashed_tasks:
            task = json.loads(row['task_json'])
            task_id = task.get('task_id')
            
            res_json = {
                'status': 'FAILED',
                'stderr': 'VERIFY_AFTER_CRASH: Worker crashed during external effect.',
                'goal_id': task.get('goal_id'),
                'task_id': task_id,
                'attempt_id': task.get('attempt_id'),
                'dispatch_id': task.get('dispatch_id'),
                'execution_ref': task.get('execution_ref'),
                'worker_id': worker_id,
                'provider': 'mac_crashed',
                'run_id': 'crashed-unknown',
                'result_id': f'result-{uuid.uuid4().hex}',
                'artifacts': []
            }
            if 'batch_id' in task: res_json['batch_id'] = task['batch_id']
            if 'prompt_id' in task: res_json['prompt_id'] = task['prompt_id']
            
            conn.execute("INSERT OR REPLACE INTO outbox (task_id, payload_json, endpoint, status) VALUES (?, ?, ?, ?)", 
                         (task_id, json.dumps(res_json), '/tasks/result', 'PENDING'))
            # Mark QUARANTINE locally so we don't pick it up again
            conn.execute("UPDATE inbox SET status = 'QUARANTINE' WHERE task_id = ?", (task_id,))
            conn.commit()
            write_log(f"Found ambiguous crash marker for task {task_id}. Quarantining locally.")

    while True:
        try:
            task = None
            with sqlite3.connect(get_db_path()) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT task_id, task_json FROM inbox WHERE status = 'QUEUED' ORDER BY added_at ASC LIMIT 1")
                row = cursor.fetchone()
                if row:
                    task = json.loads(row['task_json'])
                    conn.execute("UPDATE inbox SET status = 'RUNNING' WHERE task_id = ?", (task['task_id'],))
            
            if task:
                task_id = task.get("task_id", "UNKNOWN")
                write_log(f"Processing task {task_id}")
                try:
                    keep_awake = subprocess.Popen(["caffeinate", "-s", "-i"])
                except FileNotFoundError:
                    keep_awake = None
                    
                try:
                    mode = task.get("mode", "ANTIGRAVITY")
                    result = None
                    
                    if not task.get("task_id") or (not task.get("instruction") and not task.get("description")):
                        result = {"status": "FAILED", "reason": "MALFORMED_TASK", "stderr": "Task is missing task_id or instruction"}
                        mode = "FAILED_VALIDATION"
                        
                    target_agent = task.get("target_agent", "").lower()
                    target_capability = task.get("target_capability", "").lower()
                    if target_agent and "mac" not in target_agent and "night-captain" not in target_agent:
                        result = {"status": "FAILED", "reason": "UNQUALIFIED", "stderr": f"Target agent '{target_agent}' incompatible with Mac worker."}
                        mode = "FAILED_VALIDATION"
                    elif target_capability and target_capability not in ["", "mac", "macos", "antigravity", "linux", "copilot", "bash", "python"]:
                        result = {"status": "FAILED", "reason": "UNQUALIFIED", "stderr": f"Target capability '{target_capability}' missing on this worker."}
                        mode = "FAILED_VALIDATION"
                        
                    workspace = task.get("workspace")
                    if workspace and mode != "FAILED_VALIDATION":
                        try:
                            os.chdir(workspace)
                        except FileNotFoundError:
                            result = {"status": "FAILED", "reason": "FAILED_SCOPE", "stderr": f"Workspace {workspace} not found. Out of scope."}
                            mode = "FAILED_VALIDATION"

                    if mode != "FAILED_VALIDATION":
                        if "mac" in target_agent and mode == "ANTIGRAVITY" and "echo" in task.get("instruction", "").lower():
                            mode = "NATIVE"
                            
                        if mode == "NATIVE":
                            result = run_native(task, config)
                        elif mode == "COPILOT":
                            result = run_copilot(task, config)
                        else:
                            result = run_agy(task, config)
                            
                    if result.get("status") == "PROVIDER_WAIT":
                        write_log(f"Task {task_id} hit a provider wait: {result.get('reason')}")
                        wait_payload = {
                            "worker_id": worker_id,
                            "reason": result.get("reason", "PROVIDER_UNAVAILABLE"),
                            "wait_type": "WAITING_PROVIDER",
                            "task_id": task_id
                        }
                        with sqlite3.connect(get_db_path()) as conn:
                            conn.execute("INSERT OR REPLACE INTO outbox (task_id, payload_json, endpoint, status) VALUES (?, ?, ?, ?)", 
                                         (task_id, json.dumps(wait_payload), f"/tasks/{task_id}/provider_wait", 'PENDING'))
                            conn.execute("UPDATE inbox SET status = 'DONE' WHERE task_id = ?", (task_id,))
                        continue
                        
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
                        "worker_id": worker_id,
                        "goal_id": task.get("goal_id"),
                        "task_id": task_id,
                        "dispatch_id": task.get("dispatch_id"),
                        "attempt_id": task.get("attempt_id"),
                        "execution_ref": task.get("execution_ref"),
                        "run_id": str(uuid.uuid4()),
                        "result_id": str(uuid.uuid4()),
                        "status": result.get("status", "FAILED"),
                        "artifacts": artifact_evidence,
                        "provider": "mac_" + result.get("execution_mode", mode).lower(),
                        "raw_result": result
                    }
                    if 'batch_id' in task: payload['batch_id'] = task['batch_id']
                    if 'prompt_id' in task: payload['prompt_id'] = task['prompt_id']
                    
                    with sqlite3.connect(get_db_path()) as conn:
                        conn.execute("INSERT OR REPLACE INTO outbox (task_id, payload_json, endpoint, status) VALUES (?, ?, ?, ?)", 
                                     (task_id, json.dumps(payload), '/tasks/result', 'PENDING'))
                        conn.execute("UPDATE inbox SET status = 'DONE' WHERE task_id = ?", (task_id,))
                        
                finally:
                    if keep_awake:
                        keep_awake.terminate()
            else:
                time.sleep(config.get("POLL_INTERVAL_SECONDS", 5))
                
        except Exception as e:
            write_log(f"Error in execution loop: {e}\n{traceback.format_exc()}")
            time.sleep(5)

if __name__ == "__main__":
    loop()
