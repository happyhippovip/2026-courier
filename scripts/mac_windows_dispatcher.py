# SIMULATION / NON-PRODUCTION EVIDENCE
# THIS SCRIPT DEVIATES FROM COURIER V1 ARCHITECTURE AND WAS CREATED AS A SYNTHETIC OVERNIGHT TEST
import json
import sys
import subprocess
import time
from pathlib import Path

def run_ssh(command):
    res = subprocess.run(["ssh", "windows-ai", f"powershell -Command \"{command}\""], capture_output=True, text=True)
    return res.returncode, res.stdout.strip(), res.stderr.strip()

def dispatch_task(task_payload):
    task_id = task_payload.get("TASK_ID")
    target_host = task_payload.get("TARGET_HOST")
    project_path = task_payload.get("PROJECT_PATH")
    action = task_payload.get("ACTION")
    
    if not all([task_id, target_host, project_path, action]):
        print(json.dumps({"STATE": "FAILED", "REASON": "Missing required task fields."}))
        return "FAILED"
        
    print(f"Dispatching task {task_id}")
    
    # Check duplicate on Windows
    check_dup_cmd = f"if ((Test-Path '{project_path}\runtime\tasks\completed\{task_id}.json') -or (Test-Path '{project_path}\runtime\results\{task_id}.json')) {{ Write-Output 'DUPLICATE' }}"
    rc, out, err = run_ssh(check_dup_cmd)
    if "DUPLICATE" in out:
        print(json.dumps({"STATE": "COMPLETED_EXISTING", "REASON": "Task already completed or resulted on Windows."}))
        return "COMPLETED_EXISTING"
        
    # SCP to inbox
    tmp_file = Path(f"/tmp/{task_id}.json")
    try:
        with open(tmp_file, "w") as f:
            json.dump(task_payload, f)
            
        scp_res = subprocess.run(["scp", str(tmp_file), f"windows-ai:{project_path}\runtime\tasks\inbox\{task_id}.json"], capture_output=True)
        if scp_res.returncode != 0:
            print(json.dumps({"STATE": "FAILED", "REASON": f"SCP failed: {scp_res.stderr.decode()}"}))
            return "FAILED"
    finally:
        if tmp_file.exists():
            tmp_file.unlink()

    print(json.dumps({"STATE": "SUBMITTED", "REASON": "Task submitted to Windows inbox. Waiting for automatic consumption and result..."}))
    
    # Poll for result
    read_res_cmd = f"Get-Content -Path {project_path}\runtime\results\{task_id}.json -Raw"
    
    max_retries = 30
    rc = 1
    out = ""
    for _ in range(max_retries):
        rc, out, err = run_ssh(read_res_cmd)
        if rc == 0 and out.strip():
            break
        time.sleep(2)
        
    if rc != 0 or not out.strip():
        print(json.dumps({"STATE": "TIMEOUT", "REASON": f"Result file missing or empty after polling. err={err}"}))
        return "TIMEOUT"
        
    try:
        result_json = json.loads(out)
    except Exception as e:
        print(json.dumps({"STATE": "FAILED", "REASON": f"Result parse error: {e}"}))
        return "FAILED"
        
    # Verify TASK_ID
    if result_json.get("TaskId", result_json.get("TASK_ID")) != task_id:
        print(json.dumps({"STATE": "CONFLICT", "REASON": "Returned TASK_ID does not match."}))
        return "CONFLICT"
        
    # Return Windows EXIT_CODE / STATUS / OUTPUT
    out_payload = {
        "STATE": "RESULT_RECEIVED",
        "EXIT_CODE": result_json.get("ExitCode", result_json.get("EXIT_CODE")),
        "STATUS": result_json.get("Status", result_json.get("STATUS")),
        "OUTPUT": result_json.get("Output", result_json.get("OUTPUT"))
    }
    print(json.dumps(out_payload))
    return "RESULT_RECEIVED"

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(json.dumps({"STATE": "FAILED", "REASON": "Usage: python3 mac_windows_dispatcher.py <task_json_file>"}))
        sys.exit(1)
        
    task_file = Path(sys.argv[1])
    with open(task_file, "r") as f:
        payload = json.load(f)
        
    state = dispatch_task(payload)
    if state in ["FAILED", "TIMEOUT", "CONFLICT"]:
        sys.exit(1)
    sys.exit(0)
