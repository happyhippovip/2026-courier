import json
import re
import subprocess
import sys
import uuid

SAFE_TASK_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

def run_worker(task_path, negative_test=False):
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
    
    # We remove --dangerously-skip-permissions. A harmless task doesn't use tools and shouldn't prompt.
    dispatch_ref = str(uuid.uuid4())
    
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    pid = process.pid
    
    stdout, stderr = process.communicate(timeout=60)
    
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
        
    consume(res_json, task['task_id'], result_ref)
    return pid, dispatch_ref, result_ref

def consume(res_json, task_id, result_ref):
    try:
        with open('central_state.json', 'r') as f:
            state = json.load(f)
    except Exception:
        state = {"tasks": {}}
        
    status = res_json.get("status", "FAILED")
    
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
    
    with open('central_state.json', 'w') as f:
        json.dump(state, f, indent=2)

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "positive"
    
    if mode == "positive":
        task_id = "task-gemini-002"
        with open('dummy_task_2.json', 'w') as f:
            json.dump({"task_id": task_id, "instruction": "Respond with {'status': 'SUCCESS'}"}, f)
        run_worker('dummy_task_2.json', negative_test=False)
        
    elif mode == "negative":
        task_id = "task-gemini-003-invalid"
        with open('dummy_task_3.json', 'w') as f:
            json.dump({"task_id": task_id, "instruction": "Respond with garbage"}, f)
        run_worker('dummy_task_3.json', negative_test=True)
