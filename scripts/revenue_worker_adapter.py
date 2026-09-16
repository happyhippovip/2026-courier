import json, time, os, sys, shutil, subprocess, uuid, traceback
import base64, zipfile
from pathlib import Path
import urllib.request
import urllib.error

# Paths
BASE_DIR = Path(__file__).parent
STATE_DIR = BASE_DIR / "revenue_worker_state"
LOGS_DIR = BASE_DIR / "logs"
CONFIG_PATH = BASE_DIR / "revenue_worker_config.json"

for d in [STATE_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

def write_log(msg):
    print(msg)
    log_file = LOGS_DIR / "revenue_worker.log"
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

def get_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)
    else:
        config = {
            "WORKER_ID": f"REVENUE-MAC-{uuid.uuid4().hex[:6].upper()}",
            "POLL_INTERVAL_SECONDS": 5
        }
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)
            
    # macOS Keychain support
    try:
        pw = subprocess.check_output(["security", "find-generic-password", "-a", "courier_worker", "-s", "courier_api_key", "-w"], stderr=subprocess.DEVNULL)
        config["COURIER_API_KEY"] = pw.decode("utf-8").strip()
    except Exception:
        pass
        
    try:
        srv = subprocess.check_output(["security", "find-generic-password", "-a", "courier_worker", "-s", "courier_server_url", "-w"], stderr=subprocess.DEVNULL)
        config["COURIER_SERVER"] = srv.decode("utf-8").strip()
    except Exception:
        pass

    if "COURIER_SERVER" in os.environ:
        config["COURIER_SERVER"] = os.environ["COURIER_SERVER"]
    if "COURIER_API_KEY" in os.environ:
        config["COURIER_API_KEY"] = os.environ["COURIER_API_KEY"]
        
    if "COURIER_SERVER" not in config or "COURIER_API_KEY" not in config:
        write_log("ERROR: Missing COURIER_SERVER or COURIER_API_KEY. Exiting.")
        sys.exit(1)
        
    return config

def http_post(config, endpoint, data=None):
    url = f"{config['COURIER_SERVER']}{endpoint}"
    req = urllib.request.Request(url, method="POST")
    req.add_header("Authorization", f"Bearer {config['COURIER_API_KEY']}")
    req.add_header("Content-Type", "application/json")
    if data:
        req.data = json.dumps(data).encode("utf-8")
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        write_log(f"HTTPError: {e.code} {e.read().decode('utf-8')}")
        return None
    except Exception as e:
        write_log(f"Request failed: {e}")
        return None


import fcntl
def acquire_single_instance_lock():
    lock_file = STATE_DIR / "revenue_daemon.lock"
    lock_fd = open(lock_file, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_fd
    except BlockingIOError:
        print("Another instance of revenue worker is already running. Exiting.")
        sys.exit(0)

def main():
    _lock_fd = acquire_single_instance_lock()

    config = get_config()
    worker_id = config["WORKER_ID"]
    write_log(f"Revenue Worker {worker_id} started. Target: {config['COURIER_SERVER']}")
    
    error_backoff = 2
    while True:
        try:

            try:
                paths = [p for p in STATE_DIR.iterdir() if p.is_dir() and not p.name.startswith(".")]
                paths.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                for p in paths[5:]:
                    shutil.rmtree(p)
            except Exception:
                pass

            # Register / Heartbeat
            http_post(config, "/workers/register", {
                "worker_id": worker_id,
                "capabilities": ["revenue_safety_audit", "linux"],
                "cost_per_hour": 0.0, "cost_class": "free",
                "status": "idle"
            })
            
            # Claim task
            claim_resp = http_post(config, "/tasks/claim", {
                "worker_id": worker_id,
                "capabilities": ["revenue_safety_audit"]
            })
            
            if claim_resp and claim_resp.get("task"):
                task = claim_resp["task"]
                task_id = task["task_id"]
                attempt_id = task.get("attempt_id", task_id)
                write_log(f"Claimed task {task_id}")
                
                work_dir = STATE_DIR / task_id
                if work_dir.exists():
                    shutil.rmtree(work_dir)
                work_dir.mkdir(parents=True)
                
                task_file = work_dir / "task.json"
                task_file.write_text(json.dumps(task, indent=2))
                
                # Execute revenue worker
                write_log("Executing revenue_v1_safety_baseline.py worker...")
                cmd = [sys.executable, str(BASE_DIR / "revenue_v1_safety_baseline.py"), "worker", str(task_file), str(work_dir)]
                try:
                    result_raw = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
                    result_data = json.loads(result_raw.decode("utf-8"))
                    
                    # Package artifacts
                    zip_path = work_dir / "revenue_artifacts.zip"
                    with zipfile.ZipFile(zip_path, 'w') as zipf:
                        if (work_dir / "report.json").exists():
                            zipf.write(work_dir / "report.json", "report.json")
                        if (work_dir / "report.md").exists():
                            zipf.write(work_dir / "report.md", "report.md")
                            
                    with open(zip_path, "rb") as f:
                        artifact_bytes = f.read()
                        
                    import hashlib
                    artifact_sha = hashlib.sha256(artifact_bytes).hexdigest()
                    artifact_b64 = base64.b64encode(artifact_bytes).decode('utf-8')
                    
                    # Post result
                    res_payload = {
                        "task_id": task_id,
                        "attempt_id": attempt_id,
                        "worker_id": worker_id,
                        "result_data": result_data,
                        "artifact_name": "revenue_artifacts.zip",
                        "artifact_sha256": artifact_sha,
                        "artifact_content_base64": artifact_b64,
                        "dispatch_id": task.get("dispatch_id", "none"),
                        "goal_id": task.get("goal_id", "none"),
                        "result_id": f"res-{uuid.uuid4().hex[:8]}",
                        "run_id": f"run-{uuid.uuid4().hex[:8]}",
                        "status": "SUCCESS",
                        "artifacts": [{"path": "revenue_artifacts.zip", "sha256": artifact_sha}]
                    }
                    

                    write_log("Posting result...")
                    import random
                    post_backoff = 2
                    while True:
                        res, err = http_post(config, "/tasks/result", res_payload)
                        if err:
                            write_log(f"Result post failed: {err}. Retrying in {post_backoff}s...")
                            time.sleep(post_backoff + random.uniform(0, 2))
                            post_backoff = min(60, post_backoff * 2)
                        else:
                            write_log(f"Task {task_id} completed and posted successfully.")
                            break

                    
                except subprocess.CalledProcessError as e:
                    write_log(f"Task execution failed: {e.output.decode('utf-8', errors='ignore')}")
                    # Could implement fail endpoint here if one existed
                    
        except Exception as e:
            write_log(f"Error in main loop: {traceback.format_exc()}")
            import random
            time.sleep(error_backoff + random.uniform(0, 2))
            error_backoff = min(60, error_backoff * 2)
            continue
            
        import random
        time.sleep(config["POLL_INTERVAL_SECONDS"] + random.uniform(0, 1))
        error_backoff = 2

if __name__ == "__main__":
    main()
