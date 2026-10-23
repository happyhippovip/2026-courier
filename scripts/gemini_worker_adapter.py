import json
import os
import re
import signal
import subprocess
import sys
import uuid
from pathlib import Path


def _kill_process_tree(process: subprocess.Popen) -> None:
    """Terminate child process and its process group to prevent orphan processes."""
    pid = getattr(process, "pid", None)
    if isinstance(pid, int) and pid > 0 and pid != os.getpid():
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
                shell=False,
            )
        else:
            try:
                os.killpg(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                pass
    try:
        process.kill()
    except Exception:
        pass
    try:
        process.communicate(timeout=5)
    except Exception:
        pass


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from scripts.google_builder_worker import (
        probe_integration_surface,
        process_work_packet,
        run_google_builder_queue,
    )
except ImportError:
    try:
        from google_builder_worker import (
            probe_integration_surface,
            process_work_packet,
            run_google_builder_queue,
        )
    except ImportError:
        pass

SAFE_TASK_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

try:
    from scripts.intake_dispatcher import (
        _central_state_locked,
        load_central_state,
        save_central_state,
    )
except ImportError:
    _SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
    if _SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, _SCRIPTS_DIR)
    from intake_dispatcher import (
        _central_state_locked,
        load_central_state,
        save_central_state,
    )

def run_worker(task_path, negative_test=False, state_file="central_state.json"):
    with open(task_path, 'r') as f:
        task = json.load(f)

    task_id = task.get("task_id")
    if not isinstance(task_id, str) or not SAFE_TASK_RE.fullmatch(task_id):
        raise ValueError("task_id is not path-safe")

    if negative_test:
        prompt = f"Task: {task['task_id']}\nInstruction: Output garbage text, DO NOT output JSON."
    else:
        prompt = f"Task: {task['task_id']}\nInstruction: {task['instruction']}\nReturn ONLY a JSON object with status."
    
    print(f"Dispatching task {task['task_id']} to Antigravity Gemini Worker...")
    
    cmd = [
        "agy", 
        "-p", prompt,
        "--disable-slash-commands" 
    ]
    
    # Enforce P0 CostGate before spawning agy process
    from scripts.resource_policy import CostGate
    cost_res = CostGate.evaluate_spend_request(
        "google_antigravity_plus",
        estimated_cost_eur=task.get("estimated_cost_eur"),
        requested_action=task.get("requested_action", "EXECUTE_TASK"),
    )
    if not cost_res.get("allowed"):
        return {
            "status": "FAILED",
            "reason": f"COST_GATE_DENIED: {cost_res.get('reason')}",
            "error": cost_res.get("message", "Cost gate blocked execution"),
            "blocked": True,
        }

    # We remove --dangerously-skip-permissions. A harmless task doesn't use tools and shouldn't prompt.
    raw_timeout = task.get("timeout_seconds", 60)
    if isinstance(raw_timeout, bool) or not isinstance(raw_timeout, (int, float)) or raw_timeout <= 0:
        return {
            "status": "FAILED",
            "reason": "INVALID_TIMEOUT",
            "error": "timeout_seconds must be a positive number. Bool is not a duration.",
            "blocked": True,
        }
    dispatch_ref = str(uuid.uuid4())
    timeout_s = float(raw_timeout)

    popen_kwargs = {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "text": True}
    if os.name == "nt":
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        popen_kwargs["start_new_session"] = True

    process = subprocess.Popen(cmd, **popen_kwargs)
    pid = process.pid

    try:
        stdout, stderr = process.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        _kill_process_tree(process)
        res_json = {
            "status": "FAILED",
            "reason": "TIMEOUT",
            "error": f"Worker subprocess timed out after {timeout_s:g}s; process tree terminated.",
            "pid": pid,
            "dispatch_ref": dispatch_ref,
        }
        result_ref = f"gemini_result_{task['task_id']}.json"
        with open(result_ref, 'w') as f:
            json.dump(res_json, f, indent=2)
        consume(res_json, task['task_id'], result_ref, state_file=state_file)
        return pid, dispatch_ref, result_ref
    
    out = stdout.strip()
    
    # Parse json safely
    parsed = False
    if "```json" in out:
        out_clean = out.split("```json")[1].split("```")[0].strip()
    elif "```" in out:
        out_clean = out.split("```")[1].split("```")[0].strip()
    else:
        out_clean = out
        
    try:
        res_json = json.loads(out_clean)
        parsed = True
    except Exception:
        res_json = {
            "status": "FAILED", 
            "reason": "INVALID_RESULT", 
            "raw_diagnostic": out,
            "stderr": stderr
        }
        
    res_json["pid"] = pid
    res_json["dispatch_ref"] = dispatch_ref
    
    # If the output didn't contain JSON, we must fail closed (status should not be SUCCESS)
    if not parsed and res_json.get("status") == "SUCCESS":
        res_json["status"] = "FAILED"
        res_json["reason"] = "FORCED_FAIL_CLOSED"
        
    result_ref = f"gemini_result_{task['task_id']}.json"
    with open(result_ref, 'w') as f:
        json.dump(res_json, f, indent=2)
        
    consume(res_json, task['task_id'], result_ref, state_file=state_file)
    return pid, dispatch_ref, result_ref

def consume(res_json, task_id, result_ref, state_file="central_state.json"):
    status = res_json.get("status", "FAILED")
    
    with _central_state_locked(state_file):
        state = load_central_state(state_file)
        state["tasks"][task_id] = {
            "task_id": task_id,
            "worker_id": "gemini-local-agy",
            "platform": "antigravity",
            "dispatch_ref": res_json.get("dispatch_ref"),
            "pid": res_json.get("pid"),
            "state": "RECONCILED",
            "reconciled_status": status,
            "result_ref": result_ref,
            "last_transition": "AUTOMATIC_CONSUMPTION",
            "next_explicit_transition": "HUMAN_REVIEW_REQUIRED" if status == "SUCCESS" else "STOP_FAILED",
            "real_wall": "HUMAN_REVIEW_REQUIRED" if status == "SUCCESS" else "DIAGNOSTIC_REQUIRED"
        }
        save_central_state(state_file, state)

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "positive"
    
    if mode == "positive":
        task_id = "task-gemini-002"
        with open('dummy_task_2.json', 'w') as f:
            json.dump({"task_id": task_id, "instruction": "Respond with {'status': 'SUCCESS'}", "estimated_cost_eur": 0.0}, f)
        run_worker('dummy_task_2.json', negative_test=False)
        
    elif mode == "negative":
        task_id = "task-gemini-003-invalid"
        with open('dummy_task_3.json', 'w') as f:
            json.dump({"task_id": task_id, "instruction": "Respond with garbage", "estimated_cost_eur": 0.0}, f)
        run_worker('dummy_task_3.json', negative_test=True)
