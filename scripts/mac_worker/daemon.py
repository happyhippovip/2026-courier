import json, time, os, sys, shutil, subprocess, uuid, traceback
from pathlib import Path, PurePosixPath
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

# current_task.json records how far a claimed task got, so a restart never
# repeats an effect that may already have happened:
#   CLAIMED      -> execution has not begun; safe to run
#   STARTED      -> execution began without a durable result; never re-run
#   RESULT_READY -> result_payload is final; only (re)deliver it
#   RELEASE_PENDING -> result was rejected (4xx); release the task to the server
# Files without worker_phase come from the previous daemon, which wrote them
# right before executing, so they are treated as STARTED.
MAX_RESULT_POST_ATTEMPTS = 8

def persist_task(path, task):
    tmp_path = path.with_suffix(".tmp")
    with open(tmp_path, "w") as f:
        json.dump(task, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)

def is_retryable_post_error(err):
    # http_post reports server answers as "HTTP Error <code>: ..."; anything
    # else is a transport failure. Only transport errors and 5xx can change on
    # resend; a 4xx is the server's final answer for this payload.
    if not err.startswith("HTTP Error "):
        return True
    return err[len("HTTP Error "):].startswith("5")

def deliver_result(config, payload):
    """Post the stored result; returns DELIVERED, REJECTED or UNDELIVERED."""
    for attempt in range(MAX_RESULT_POST_ATTEMPTS):
        res, err = http_post(config, "/tasks/result", payload)
        if not err:
            write_log(f"Result posted successfully: {res}")
            return "DELIVERED"
        if not is_retryable_post_error(err):
            write_log(f"Result rejected permanently: {err}")
            return "REJECTED"
        write_log(f"Result post failed: {err}. Retrying in {2**attempt}s...")
        time.sleep(2 ** attempt)
    return "UNDELIVERED"

def is_safe_artifact_path(name):
    """Artifacts are relative to the worker's cwd; reject absolute and '..' paths
    (same rule as the integration contract) before anything is read."""
    if not isinstance(name, str) or not name:
        return False
    pure = PurePosixPath(name)
    return not pure.is_absolute() and ".." not in pure.parts

def collect_artifact_evidence(task, result):
    """Hash expected artifacts; any unsafe, missing or absent evidence makes it FAILED."""
    import hashlib
    evidence = []
    if result.get("status") != "SUCCESS":
        return evidence
    for expected in task.get("artifacts", []):
        name = expected.get("path") if isinstance(expected, dict) else expected
        if not is_safe_artifact_path(name):
            problem = f"Unsafe artifact path: {name}"
        elif not Path(name).is_file():
            problem = f"Missing artifact: {name}"
        else:
            evidence.append({"path": name, "sha256": hashlib.sha256(Path(name).read_bytes()).hexdigest()})
            continue
        result["status"] = "FAILED"
        result["stderr"] = result.get("stderr", "") + "\n" + problem
        return []
    if not evidence:
        result["status"] = "FAILED"
        result["stderr"] = result.get("stderr", "") + "\nNo artifact evidence for success"
    return evidence

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
    if not str(config.get("COURIER_API_KEY") or "").strip():
        write_log("FATAL: COURIER_API_KEY is not set (keychain or environment); refusing to contact the server.")
        sys.exit(2)
    current_task_state_file = STATE_DIR / "current_task.json"
    
    # Load previously claimed task for duplicate protection
    task = None
    release_ambiguous_task = False
    if current_task_state_file.exists():
        with open(current_task_state_file, 'r') as f:
            task = json.load(f)
        if task.get("worker_phase") not in ("CLAIMED", "RESULT_READY"):
            task["worker_phase"] = "STARTED"
        write_log(f"Found unfinished task {task['task_id']} in phase {task['worker_phase']}, resuming...")

    registered = False

    while True:
        try:
            if task and task.get("worker_phase") == "STARTED":
                # Interrupted mid-execution (restart or exception): the effect may
                # already exist, so never replay it. Re-registering without the
                # task hands it to Courier's restart recovery (HUMAN_REQUIRED,
                # WORKER_RESTARTED_AND_LOST_STATE).
                write_log(f"Task {task['task_id']} was interrupted during execution; not re-running it.")
                release_ambiguous_task = True
                registered = False
                task = None

            if not registered:
                reg_payload = {
                    "worker_id": config["WORKER_ID"],
                    "platform": "macos",
                    "capabilities": ["macos", "linux", "antigravity"]
                }
                if release_ambiguous_task:
                    reg_payload["current_task"] = None
                res, err = http_post(config, "/workers/register", reg_payload)
                if err:
                    write_log(f"Failed to register: {err}")
                    time.sleep(5) # backoff
                    continue
                write_log("Registered successfully.")
                registered = True
                if release_ambiguous_task:
                    os.remove(current_task_state_file)
                    release_ambiguous_task = False
                
            # Heartbeat
            res, err = http_post(config, "/workers/heartbeat", {"worker_id": config["WORKER_ID"]})
            if err:
                write_log(f"Heartbeat failed: {err}")
                registered = False
                time.sleep(5)
                continue
                
            if not task:
                # Claim Task
                res, err = http_post(config, "/tasks/claim", {"worker_id": config["WORKER_ID"]})
                if err:
                    write_log(f"Claim failed: {err}")
                    time.sleep(5)
                    continue
                    
                task = res.get("task")
                if task:
                    task["worker_phase"] = "CLAIMED"
                    persist_task(current_task_state_file, task)

            if task and task.get("worker_phase") == "CLAIMED":
                write_log(f"Processing task {task['task_id']}")
                task["worker_phase"] = "STARTED"
                persist_task(current_task_state_file, task)
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
                artifact_evidence = collect_artifact_evidence(task, result)
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
                task["result_payload"] = payload
                task["worker_phase"] = "RESULT_READY"
                persist_task(current_task_state_file, task)

            if task:
                outcome = deliver_result(config, task["result_payload"])
                if outcome == "UNDELIVERED":
                    # Keep the finished result; later cycles only redeliver it.
                    write_log(f"Result for task {task['task_id']} not delivered yet; keeping it for redelivery.")
                elif outcome == "REJECTED":
                    persist_task(STATE_DIR / f"rejected_result_{task['task_id']}.json", task)
                    # The server keeps the task assigned after a 4xx; release it (persisted
                    # first, so a crash still releases on restart) instead of WORKER_BUSY forever.
                    task["worker_phase"] = "RELEASE_PENDING"
                    persist_task(current_task_state_file, task)
                    write_log(f"Result for task {task['task_id']} rejected; releasing it to Courier recovery.")
                    release_ambiguous_task = True
                    registered = False
                    task = None
                else:
                    os.remove(current_task_state_file)
                    task = None
                
        except Exception as e:
            write_log(f"Error in HTTP poll loop: {e}\n{traceback.format_exc()}")
            
        time.sleep(config.get("POLL_INTERVAL_SECONDS", 5))

if __name__ == "__main__":
    loop()
