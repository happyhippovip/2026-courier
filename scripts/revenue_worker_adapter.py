import json, time, os, sys, shutil, subprocess, uuid, traceback, hashlib
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


class ResultPostError(RuntimeError):
    pass


def validate_task_identity(task):
    required = ("goal_id", "task_id", "attempt_id", "dispatch_id", "execution_ref")
    missing = [field for field in required if not isinstance(task.get(field), str) or not task[field]]
    if missing:
        raise ValueError("TaskPacket is missing identity fields: " + ", ".join(missing))
    return task


def work_dir_for_task(task):
    validate_task_identity(task)
    digest = hashlib.sha256(task["dispatch_id"].encode("utf-8")).hexdigest()
    return STATE_DIR / f"dispatch-{digest}"


def result_id_for(task):
    validate_task_identity(task)
    return f"result-{task['dispatch_id']}"


def persist_pending_result(work_dir, payload):
    destination = work_dir / "pending_result.json"
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    work_dir.mkdir(parents=True, exist_ok=True)
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError:
            if destination.is_symlink() or not destination.is_file():
                raise RuntimeError("pending result path is not a regular owned file")
            existing = json.loads(destination.read_text(encoding="utf-8"))
            if existing != payload:
                raise RuntimeError("conflicting pending result already exists for dispatch")
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def persist_posted_marker(work_dir, payload, acknowledgement):
    destination = work_dir / "posted_result.json"
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    marker = {
        "result_id": payload.get("result_id"),
        "acknowledgement": acknowledgement,
    }
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(marker, handle, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def persist_task_checkpoint(work_dir, task):
    destination = work_dir / "task.json"
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(task, handle, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError:
            if destination.is_symlink() or not destination.is_file():
                raise RuntimeError("task checkpoint is not a regular owned file")
            if json.loads(destination.read_text(encoding="utf-8")) != task:
                raise RuntimeError("conflicting task checkpoint already exists for dispatch")
    finally:
        temporary.unlink(missing_ok=True)
    return destination

def write_log(msg):
    print(msg)
    with open(LOGS_DIR / "revenue_worker.log", "a") as f:
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

    # Windows / cross-platform Keyring support
    try:
        import keyring
        if not config.get("COURIER_API_KEY"):
            pw = keyring.get_password("courier_worker", "courier_api_key")
            if pw:
                config["COURIER_API_KEY"] = pw
        if not config.get("COURIER_SERVER"):
            srv = keyring.get_password("courier_worker", "courier_server_url")
            if srv:
                config["COURIER_SERVER"] = srv
    except ImportError:
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


def post_result(config, payload):
    response = http_post(config, "/tasks/result", payload)
    status = response.get("status") if isinstance(response, dict) else None
    if status not in {"ACK_RESULT_RECEIVED", "ACK_DUPLICATE"}:
        raise ResultPostError(f"result was not canonically acknowledged: {status or 'NO_RESPONSE'}")
    return status


def deliver_pending_result(config, work_dir):
    pending = work_dir / "pending_result.json"
    if not pending.is_file():
        return False
    if pending.is_symlink():
        raise RuntimeError("pending result must be a regular owned file")
    payload = json.loads(pending.read_text(encoding="utf-8"))
    acknowledgement = post_result(config, payload)
    persist_posted_marker(work_dir, payload, acknowledgement)
    pending.unlink()
    return True


def flush_pending_results(config):
    for pending in sorted(STATE_DIR.glob("dispatch-*/pending_result.json")):
        deliver_pending_result(config, pending.parent)


def recover_incomplete_tasks(config, worker_id):
    incomplete = []
    for task_file in sorted(STATE_DIR.glob("dispatch-*/task.json")):
        work_dir = task_file.parent
        if task_file.is_symlink() or not task_file.is_file():
            raise RuntimeError("persisted revenue task must be a regular owned file")
        task = json.loads(task_file.read_text(encoding="utf-8"))
        validate_task_identity(task)
        if work_dir_for_task(task) != work_dir:
            raise RuntimeError("persisted revenue task path does not match dispatch identity")
        if task.get("worker_id") not in {None, worker_id}:
            raise RuntimeError("persisted revenue task belongs to another worker")
        if (work_dir / "pending_result.json").is_file():
            continue
        posted = work_dir / "posted_result.json"
        if posted.exists():
            if posted.is_symlink() or not posted.is_file():
                raise RuntimeError("posted result marker must be a regular owned file")
            marker = json.loads(posted.read_text(encoding="utf-8"))
            if marker != {
                "result_id": result_id_for(task),
                "acknowledgement": marker.get("acknowledgement"),
            } or marker.get("acknowledgement") not in {"ACK_RESULT_RECEIVED", "ACK_DUPLICATE"}:
                raise RuntimeError("posted result marker is not bound to the persisted task")
            continue
        incomplete.append(task)

    if len(incomplete) > 1:
        raise RuntimeError("multiple incomplete revenue tasks require reconciliation")
    if incomplete:
        write_log(f"Resuming incomplete revenue task {incomplete[0]['task_id']} before new claim.")
        process_claimed_task(config, worker_id, incomplete[0], resume=True)
        return True
    return False


def process_claimed_task(config, worker_id, task, resume=False):
    validate_task_identity(task)
    task_id = task["task_id"]
    attempt_id = task["attempt_id"]
    work_dir = work_dir_for_task(task)
    if not resume:
        if work_dir.exists():
            shutil.rmtree(work_dir, ignore_errors=True)
        work_dir.mkdir(parents=True, exist_ok=True)
        task_file = persist_task_checkpoint(work_dir, task)
    else:
        task_file = work_dir / "task.json"

    write_log("Executing revenue_v1_safety_baseline.py worker...")
    cmd = [sys.executable, str(BASE_DIR / "revenue_v1_safety_baseline.py"), "worker", str(task_file), str(work_dir)]
    try:
        result_raw = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        result_data = json.loads(result_raw.decode("utf-8"))

        zip_path = work_dir / "revenue_artifacts.zip"
        with zipfile.ZipFile(zip_path, "w") as zipf:
            if (work_dir / "report.json").exists():
                zipf.write(work_dir / "report.json", "report.json")
            if (work_dir / "report.md").exists():
                zipf.write(work_dir / "report.md", "report.md")

        artifact_bytes = zip_path.read_bytes()
        artifact_sha = hashlib.sha256(artifact_bytes).hexdigest()
        artifact_b64 = base64.b64encode(artifact_bytes).decode("utf-8")
        res_payload = {
            "goal_id": task["goal_id"],
            "task_id": task_id,
            "attempt_id": attempt_id,
            "dispatch_id": task["dispatch_id"],
            "execution_ref": task["execution_ref"],
            "worker_id": worker_id,
            "run_id": task["execution_ref"],
            "result_id": result_id_for(task),
            "status": "SUCCESS",
            "artifacts": [{"path": "revenue_artifacts.zip", "sha256": artifact_sha}],
            "result_data": result_data,
            "artifact_name": "revenue_artifacts.zip",
            "artifact_sha256": artifact_sha,
            "artifact_content_base64": artifact_b64,
        }
        write_log("Posting result...")
        persist_pending_result(work_dir, res_payload)
        deliver_pending_result(config, work_dir)
        write_log(f"Task {task_id} completed.")
        return True
    except ResultPostError as exc:
        write_log(f"Result delivery pending for task {task_id}: {exc}")
        return False
    except subprocess.CalledProcessError as exc:
        error = exc.output.decode("utf-8", errors="ignore")
        write_log(f"Task execution failed: {error}")
    except Exception as exc:
        error = str(exc)
        write_log(f"Error executing task: {traceback.format_exc()}")

    failure_payload = {
        "goal_id": task["goal_id"],
        "task_id": task_id,
        "attempt_id": attempt_id,
        "dispatch_id": task["dispatch_id"],
        "execution_ref": task["execution_ref"],
        "worker_id": worker_id,
        "run_id": task["execution_ref"],
        "result_id": result_id_for(task),
        "status": "FAILED_TERMINAL",
        "artifacts": [],
        "error": error[:500],
    }
    persist_pending_result(work_dir, failure_payload)
    deliver_pending_result(config, work_dir)
    return False

def main():
    config = get_config()
    worker_id = config["WORKER_ID"]
    write_log(f"Revenue Worker {worker_id} started. Target: {config['COURIER_SERVER']}")
    
    while True:
        try:
            # Result delivery is resumed before any new claim. An uncertain
            # transport outcome never becomes a contradictory failure result.
            flush_pending_results(config)
            if recover_incomplete_tasks(config, worker_id):
                time.sleep(config["POLL_INTERVAL_SECONDS"])
                continue

            # Register / Heartbeat
            http_post(config, "/workers/register", {
                "worker_id": worker_id,
                "capabilities": ["revenue_safety_audit", "linux"],
                "cost_per_hour": 1.0,
                "status": "idle"
            })
            
            # Claim task
            claim_resp = http_post(config, "/tasks/claim", {
                "worker_id": worker_id,
                "capabilities": ["revenue_safety_audit"]
            })
            
            if claim_resp and claim_resp.get("task"):
                task = claim_resp["task"]
                validate_task_identity(task)
                task_id = task["task_id"]
                write_log(f"Claimed task {task_id}")
                process_claimed_task(config, worker_id, task)
                    
        except Exception as e:
            write_log(f"Error in main loop: {traceback.format_exc()}")
            
        time.sleep(config["POLL_INTERVAL_SECONDS"])

if __name__ == "__main__":
    main()
