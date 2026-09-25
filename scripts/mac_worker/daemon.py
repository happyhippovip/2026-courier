import json, time, os, sys, shutil, subprocess, uuid, traceback, fcntl
from pathlib import Path, PurePosixPath
import urllib.request
import urllib.error
import urllib.parse
import signal
from contextlib import nullcontext

# Paths
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR.resolve()))
from runtime_state import (CANONICAL_WORKSPACE, atomic_json, control_lock, read_object,
                           process_identity, same_process, cleanup_group, group_exists)
CONFIG_PATH = Path(os.environ.get("COURIER_WORKER_CONFIG", BASE_DIR / "config.json"))
# A supervisor slot runs its own daemon with its own home, so each slot has
# isolated task state (current_task.json) and logs.
WORKER_HOME = Path(os.environ["COURIER_WORKER_HOME"]) if os.environ.get("COURIER_WORKER_HOME") else None
STATE_DIR = WORKER_HOME / "state" if WORKER_HOME else BASE_DIR / "state"
LOGS_DIR = WORKER_HOME / "logs" if WORKER_HOME else BASE_DIR / "logs"

def load_config():
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)
    
    # Try reading from macOS keychain
    try:
        pw = subprocess.check_output(["security", "find-generic-password", "-a", "courier_worker", "-s", "courier_api_key", "-w"], stderr=subprocess.DEVNULL)
        config["COURIER_API_KEY"] = pw.decode("utf-8").strip()
    except (subprocess.CalledProcessError, OSError):
        pass
        
    try:
        srv = subprocess.check_output(["security", "find-generic-password", "-a", "courier_worker", "-s", "courier_server_url", "-w"], stderr=subprocess.DEVNULL)
        config["COURIER_SERVER"] = srv.decode("utf-8").strip()
    except (subprocess.CalledProcessError, OSError):
        pass
    
    # Environment overrides
    if "COURIER_SERVER" in os.environ:
        config["COURIER_SERVER"] = os.environ["COURIER_SERVER"]
    if "COURIER_API_KEY" in os.environ:
        config["COURIER_API_KEY"] = os.environ["COURIER_API_KEY"]
    if os.environ.get("COURIER_WORKER_ID"):
        config["WORKER_ID"] = os.environ["COURIER_WORKER_ID"]
        
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
    atomic_json(path, task)


def worker_wall():
    value = os.environ.get("COURIER_WALL_DIR")
    return Path(value) if value else None


def admission_lock():
    wall = worker_wall()
    return control_lock(wall) if wall else nullcontext()


def stopped():
    wall = worker_wall()
    return bool(wall and (wall / "STOP").exists())


def resource_ready():
    if not worker_wall():
        return True  # Non-wall legacy worker; supervised Muse always has a wall.
    from muse_supervisor import CapacityGovernor
    return CapacityGovernor(1).evaluate() > 0


class MuseAdmissionBlocked(Exception):
    """No child has been spawned; retaining CLAIMED is safe."""


class WorkerShutdown(BaseException):
    pass


def artifact_path(task, name):
    return Path(task.get("workspace") or ".") / name


def bind_runtime_task(task, config):
    mode = task.get("mode", os.environ.get("COURIER_WORKER_DEFAULT_MODE", "ANTIGRAVITY"))
    if mode != "MUSE":
        return
    import muse_adapter
    binding = muse_adapter.task_binding(task, os.environ.get("COURIER_SLOT_ID") or config["WORKER_ID"],
        os.environ.get("COURIER_MUSE_WORKSPACE", config.get("MUSE_WORKSPACE", CANONICAL_WORKSPACE)))
    if task.get("runtime_binding") and task["runtime_binding"] != binding:
        raise muse_adapter.MuseBindingError("Restored runtime binding mismatch; reconciliation required")
    task["runtime_binding"] = binding
    if task.get("workspace") and task["workspace"] != binding["workspace"]:
        raise muse_adapter.MuseBindingError("Restored artifact workspace mismatch")
    payload = task.get("result_payload")
    if payload and any(payload.get(key) != task.get(key)
                       for key in (*muse_adapter.IDENTITY_FIELDS, "worker_id")):
        raise muse_adapter.MuseBindingError("Stored result identity differs from its task")


def require_no_orphan():
    previous = read_object(STATE_DIR / "muse_process.json")
    if previous and previous.get("state") != "CLEAN":
        identity = previous.get("identity")
        if not identity or group_exists(identity["pgid"]):
            raise RuntimeError("Unreconciled Muse child; no further claims/executions allowed")


def persist_ready_result(path, task, config):
    result = task["result_payload"].get("raw_result", {})
    if result.get("execution_mode") == "MUSE":
        import muse_adapter
        muse_adapter.save_checkpoint(STATE_DIR, task, result,
            slot_id=os.environ.get("COURIER_SLOT_ID") or config["WORKER_ID"],
            workspace=os.environ.get("COURIER_MUSE_WORKSPACE", config.get("MUSE_WORKSPACE", CANONICAL_WORKSPACE)))
    persist_task(path, task)

def is_retryable_post_error(err):
    # http_post reports server answers as "HTTP Error <code>: ..."; anything
    # else is a transport failure. Only transport errors and 5xx can change on
    # resend; a 4xx is the server's final answer for this payload.
    if not err.startswith("HTTP Error "):
        return True
    return err[len("HTTP Error "):].startswith("5")

def upload_enabled(config):
    """Artifact upload needs the server artifact store (P3 cutover); opt-in until then."""
    flag = os.environ.get("COURIER_ARTIFACT_UPLOAD", str(config.get("ARTIFACT_UPLOAD", "")))
    return str(flag).strip().lower() in ("1", "true", "yes")

def http_upload(config, meta, data):
    """POST raw artifact bytes; returns (record, err) like http_post."""
    req = urllib.request.Request(config["COURIER_SERVER"].rstrip("/") + "/artifacts", method="POST")
    req.add_header("Authorization", f"Bearer {config.get('COURIER_API_KEY', '')}")
    req.add_header("Content-Type", "application/octet-stream")
    req.add_header("X-Courier-Artifact", json.dumps(meta, separators=(",", ":")))
    try:
        with urllib.request.urlopen(req, data=data, timeout=30) as response:
            return json.loads(response.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP Error {e.code}: {e.read().decode('utf-8', 'replace')}"
    except Exception as e:
        return None, str(e)

def upload_pending_artifacts(config, task, state_file):
    """Attach server artifact_ids to the stored result; READY|REJECTED|UNDELIVERED."""
    import hashlib
    for art in task["result_payload"].get("artifacts", []):
        if "artifact_id" in art:
            continue
        name = art["path"]
        if not is_safe_artifact_path(name) or not artifact_path(task, name).is_file():
            return "REJECTED"
        data = artifact_path(task, name).read_bytes()
        if hashlib.sha256(data).hexdigest() != art["sha256"]:
            write_log(f"Artifact {name} changed after hashing; not uploading.")
            return "REJECTED"
        meta = {"name": name, "sha256": art["sha256"], "size": len(data),
                **{f: task.get(f) for f in ("goal_id", "task_id", "attempt_id", "dispatch_id", "worker_id")}}
        record, err = http_upload(config, meta, data)
        if err:
            write_log(f"Artifact upload failed: {err.split(':')[0]}")
            return "UNDELIVERED" if is_retryable_post_error(err) else "REJECTED"
        if record.get("sha256") != art["sha256"] or record.get("size") != len(data) or not str(record.get("artifact_id", "")).startswith("art-"):
            return "REJECTED"
        art["artifact_id"], art["size"] = record["artifact_id"], record["size"]
        persist_task(state_file, task)
    return "READY"

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
        elif not artifact_path(task, name).is_file():
            problem = f"Missing artifact: {name}"
        else:
            evidence.append({"path": name, "sha256": hashlib.sha256(artifact_path(task, name).read_bytes()).hexdigest()})
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

def run_muse(task, config):
    """Muse slot execution through the muse_adapter boundary (no guessed CLI method)."""
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    import muse_adapter
    write_log(f"Running MUSE task {task['task_id']}")
    slot = os.environ.get("COURIER_SLOT_ID") or config["WORKER_ID"]
    workspace = os.environ.get("COURIER_MUSE_WORKSPACE", config.get("MUSE_WORKSPACE", CANONICAL_WORKSPACE))
    binding = muse_adapter.task_binding(task, slot, workspace)
    bind_runtime_task(task, config)
    checkpoint = muse_adapter.load_checkpoint(STATE_DIR)
    action = task.get("muse_action", "exec")
    if checkpoint and checkpoint.get("binding") != binding:
        # Preserve evidence, but never feed another task's context to this task.
        atomic_json(STATE_DIR / ("checkpoint.quarantine-" + uuid.uuid4().hex + ".json"), checkpoint)
        if action != "exec":
            raise muse_adapter.MuseBindingError("Foreign checkpoint cannot authorize resume")
        checkpoint = {}
    caps = muse_adapter.cli_capabilities(config)
    prompt = muse_adapter.prepare_prompt(STATE_DIR, task, binding, checkpoint, caps)
    argv, _ = muse_adapter.build_muse_command(task, checkpoint, caps, slot_id=slot,
                                             workspace=workspace, action=action, prompt=prompt)
    child_file = STATE_DIR / "muse_process.json"
    require_no_orphan()
    proc = None
    identity = None
    task["workspace"] = workspace
    persist_task(STATE_DIR / "current_task.json", task)
    # Durable output survives daemon interruption. Bounded by size and wall time.
    with open(STATE_DIR / "muse.stdout", "w+") as out, open(STATE_DIR / "muse.stderr", "w+") as err:
        try:
            with admission_lock():
                if stopped() or not resource_ready():
                    raise MuseAdmissionBlocked("STOP or resource admission denied")
                atomic_json(child_file, {"state": "STARTING", "binding": binding})
                proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                        start_new_session=True)
                identity = process_identity(proc.pid)
                atomic_json(child_file, {"state": "RUNNING", "identity": identity, "binding": binding})
            deadline = time.monotonic() + min(float(config.get("MUSE_TIMEOUT_SECONDS", 3600)), 3600)
            heartbeat_at = time.monotonic() + 30
            while proc.poll() is None:
                if time.monotonic() >= deadline or out.tell() + err.tell() > 8 * 1024 * 1024:
                    raise RuntimeError("Muse execution ambiguous: timeout/output limit; reconcile, do not retry")
                if time.monotonic() >= heartbeat_at:
                    if config.get("COURIER_SERVER"):
                        http_post(config, "/workers/heartbeat", {"worker_id": config["WORKER_ID"]})
                    heartbeat_at = time.monotonic() + 30
                time.sleep(0.1)
            if proc.returncode != 0:
                raise RuntimeError("Muse nonzero exit has ambiguous effects; reconcile, do not retry")
            out.seek(0); err.seek(0)
            result = muse_adapter.parse_result(out.read(8 * 1024 * 1024), proc.returncode, caps)
            result["stderr"] = err.read(8 * 1024 * 1024)[-4000:]
        finally:
            if proc is not None:
                clean = cleanup_group(proc, identity)
                atomic_json(child_file, {"state": "CLEAN" if clean else "ORPHANS_REMAIN",
                                         "identity": identity, "binding": binding})
                if not clean:
                    raise RuntimeError("Muse child cleanup unproven; no new execution allowed")
    return result

def acquire_worker_lock():
    """One daemon per state directory: a second one would re-claim or re-send."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    handle = open(STATE_DIR / "worker.lock", "w")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle

def loop():
    worker_lock = acquire_worker_lock()
    if worker_lock is None:
        print("Another worker daemon already owns this state directory; exiting.")
        sys.exit(3)
    # Supervisor slots: exit 0 after one task is delivered or released, so the
    # slot restarts with a fresh process; task state survives in current_task.json.
    one_task = os.environ.get("COURIER_WORKER_ONE_TASK") == "1"
    write_log("Starting Mac Worker HTTP Daemon...")
    config = load_config()
    require_no_orphan()
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
        if task.get("worker_phase") not in ("CLAIMED", "RESULT_READY", "RECOVERY_BLOCKED"):
            task["worker_phase"] = "STARTED"
        write_log(f"Found unfinished task {task['task_id']} in phase {task['worker_phase']}, resuming...")
        if task.get("worker_id") and task["worker_id"] != config["WORKER_ID"]:
            raise RuntimeError("Restored task belongs to another worker; reconciliation required")
        if (task.get("worker_phase") == "CLAIMED"
                and task.get("mode", os.environ.get("COURIER_WORKER_DEFAULT_MODE")) == "MUSE"
                and not task.get("runtime_binding")):
            raise RuntimeError("Legacy unbound Muse claim requires reconciliation before execution")
        bind_runtime_task(task, config)

    registered = False

    while True:
        try:
            if task and task.get("worker_phase") == "RECOVERY_BLOCKED":
                # Storage failure during/after execution must not release and drain
                # another task. Preserve the marker when storage becomes writable.
                try:
                    persist_task(current_task_state_file, task)
                except OSError:
                    pass
                time.sleep(config.get("POLL_INTERVAL_SECONDS", 5))
                continue
            if stopped() and (not task or task.get("worker_phase") == "CLAIMED"):
                return
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
                with admission_lock():
                    if stopped():
                        return
                    require_no_orphan()
                    if not resource_ready():
                        res, err = {"task": None}, None
                    else:
                        res, err = http_post(config, "/tasks/claim", {"worker_id": config["WORKER_ID"]})
                if err:
                    write_log(f"Claim failed: {err}")
                    time.sleep(5)
                    continue
                    
                task = res.get("task")
                if task:
                    bind_runtime_task(task, config)
                    task["worker_phase"] = "CLAIMED"
                    persist_task(current_task_state_file, task)

            if task and task.get("worker_phase") == "CLAIMED":
                if task.get("worker_id") and task["worker_id"] != config["WORKER_ID"]:
                    raise RuntimeError("Claimed task worker mismatch")
                with admission_lock():
                    if stopped():
                        return
                write_log(f"Processing task {task['task_id']}")
                task["worker_phase"] = "STARTED"
                persist_task(current_task_state_file, task)
                mode = task.get("mode", os.environ.get("COURIER_WORKER_DEFAULT_MODE", "ANTIGRAVITY"))
                # Fallback to NATIVE if requested via target_agent routing
                target = task.get("target_agent", "").lower()
                if "mac" in target and mode == "ANTIGRAVITY" and "echo" in task.get("instruction", "").lower():
                    # For simple testing/canary routing we force NATIVE if they specify echo
                    mode = "NATIVE"

                if mode == "NATIVE":
                    result = run_native(task, config)
                elif mode == "MUSE":
                    try:
                        result = run_muse(task, config)
                    except MuseAdmissionBlocked:
                        task["worker_phase"] = "CLAIMED"
                        persist_task(current_task_state_file, task)
                        time.sleep(config.get("POLL_INTERVAL_SECONDS", 5))
                        continue
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
                task["worker_phase"] = "RESULT_PENDING"

            if task and task.get("worker_phase") == "RESULT_PENDING":
                # Do not advance in-memory state until the durable write succeeded.
                # On ENOSPC we retain this same result and IDs, retry only persistence,
                # and neither send a success nor claim/execute another task.
                durable = dict(task, worker_phase="RESULT_READY")
                persist_ready_result(current_task_state_file, durable, config)
                task = durable

            if task:
                outcome = upload_pending_artifacts(config, task, current_task_state_file) if upload_enabled(config) else "READY"
                if outcome == "READY":
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
                    if one_task:
                        write_log("Task delivered; exiting for a fresh slot process.")
                        return
                
        except OSError as e:
            if task and task.get("worker_phase") == "STARTED":
                task.update(worker_phase="RECOVERY_BLOCKED", blocker="EXECUTION_STORAGE_FAILURE")
            print(f"Storage failure: {type(e).__name__}; result/task retained, no completion acknowledged.")
        except Exception as e:
            write_log(f"Error in HTTP poll loop: {e}\n{traceback.format_exc()}")
            
        time.sleep(config.get("POLL_INTERVAL_SECONDS", 5))

if __name__ == "__main__":
    def shutdown(signum, frame):
        raise WorkerShutdown()
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    try:
        loop()
    except WorkerShutdown:
        pass
