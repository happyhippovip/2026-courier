import re

with open(r"C:\Users\lol\2026-workspace\courier\scripts\windows_worker\daemon.py", "r") as f:
    content = f.read()

# Replace http_post signature
new_http_post = """def http_post(config, endpoint, data):
    url = config["COURIER_SERVER"].rstrip("/") + endpoint
    req = urllib.request.Request(url, method="POST")
    req.add_header("Content-Type", "application/json")
    if config.get("COURIER_API_KEY"):
        req.add_header("Authorization", f"Bearer {config['COURIER_API_KEY']}")
    
    jsondata = json.dumps(data).encode("utf-8")
    
    try:
        with urllib.request.urlopen(req, data=jsondata, timeout=10) as response:
            return json.loads(response.read().decode("utf-8")), None, response.getcode()
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        return None, f"HTTP Error {e.code}: {err_msg}", e.code
    except Exception as e:
        return None, str(e), None"""

content = re.sub(r'def http_post\(config, endpoint, data\):.*?return None, str\(e\)', new_http_post, content, flags=re.DOTALL)

# Replace loop
new_loop = """def get_lock():
    import msvcrt
    import sys
    lock_file_path = STATE_DIR / "daemon.lock"
    lock_file = open(lock_file_path, "w")
    try:
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        return lock_file
    except IOError:
        write_log("Another instance of the daemon is already running.")
        sys.exit(1)

def loop():
    import sys
    _lock = get_lock()
    write_log("Starting Windows Worker HTTP Daemon...")
    config = load_config()
    current_task_state_file = STATE_DIR / "current_task.json"
    current_result_state_file = STATE_DIR / "current_result.json"
    
    task = None
    pending_payload = None
    
    if current_result_state_file.exists():
        write_log("Found unfinished result POST from previous run, resuming without re-execution...")
        with open(current_result_state_file, 'r') as f:
            pending_payload = json.load(f)
            
    elif current_task_state_file.exists():
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
                res, err, status_code = http_post(config, "/workers/register", reg_payload)
                if status_code in [401, 403]:
                    write_log(f"FATAL: Permanent auth failure during register: {err}")
                    sys.exit(1)
                if err:
                    write_log(f"Failed to register: {err}")
                    time.sleep(5)
                    continue
                write_log("Registered successfully.")
                registered = True
                
            res, err, status_code = http_post(config, "/workers/heartbeat", {"worker_id": config["WORKER_ID"]})
            if status_code in [401, 403]:
                write_log(f"FATAL: Permanent auth failure during heartbeat: {err}")
                sys.exit(1)
            if err:
                write_log(f"Heartbeat failed: {err}")
                registered = False
                time.sleep(5)
                continue
                
            if not task and not pending_payload:
                res, err, status_code = http_post(config, "/tasks/claim", {"worker_id": config["WORKER_ID"]})
                if status_code in [401, 403]:
                    write_log(f"FATAL: Permanent auth failure during claim: {err}")
                    sys.exit(1)
                if err:
                    write_log(f"Claim failed: {err}")
                    time.sleep(5)
                    continue
                    
                task = res.get("task")
                if task:
                    with open(current_task_state_file, 'w') as f:
                        json.dump(task, f)
                        
            if task and not pending_payload:
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
                            result['stderr'] = result.get('stderr', '') + f'\\nMissing artifact: {expected_path}'
                            
                pending_payload = {
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
                
                with open(current_result_state_file, 'w') as f:
                    json.dump(pending_payload, f)
                    
            if pending_payload:
                retries = 0
                posted = False
                while retries < 8:
                    res, err, status_code = http_post(config, "/tasks/result", pending_payload)
                    if status_code in [400, 409]:
                        write_log(f"Permanent rejection from server (HTTP {status_code}): {err}. Discarding task.")
                        posted = True
                        break
                    if err:
                        write_log(f"Result post failed: {err}. Retrying in {2**retries}s...")
                        time.sleep(2 ** retries)
                        retries += 1
                    else:
                        write_log(f"Result posted successfully: {res}")
                        posted = True
                        break
                        
                if posted:
                    if current_task_state_file.exists():
                        os.remove(current_task_state_file)
                    if current_result_state_file.exists():
                        os.remove(current_result_state_file)
                    task = None
                    pending_payload = None
                else:
                    write_log("FATAL: Exhausted retries posting result. Failing closed to preserve state.")
                    sys.exit(1)
                
        except Exception as e:
            write_log(f"Error in HTTP poll loop: {e}\\n{traceback.format_exc()}")
            
        time.sleep(config.get("POLL_INTERVAL_SECONDS", 5))

if __name__ == "__main__":
    loop()
"""

content = re.sub(r'def loop\(\):.*', new_loop, content, flags=re.DOTALL)

with open(r"C:\Users\lol\2026-workspace\courier\scripts\windows_worker\daemon.py", "w") as f:
    f.write(content)
