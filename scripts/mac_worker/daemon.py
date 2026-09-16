import json, time, os, sys, shutil, subprocess, glob, uuid, traceback
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
STATE_DIR = BASE_DIR / "state"
INBOX_DIR = BASE_DIR / "inbox"
OUTBOX_DIR = BASE_DIR / "outbox"
LOGS_DIR = BASE_DIR / "logs"

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def write_log(msg):
    print(msg)
    with open(LOGS_DIR / "worker.log", "a") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")

def fetch_task_local(config):
    for task_file in glob.glob(str(INBOX_DIR / "*.json")):
        if task_file.endswith(".claimed"): continue
        claimed_file = task_file + ".claimed"
        try:
            os.rename(task_file, claimed_file)
            with open(claimed_file, 'r') as f:
                task = json.load(f)
            return claimed_file, task
        except OSError:
            pass
    return None, None

def run_native(task, config):
    write_log(f"Running NATIVE task {task['task_id']}")
    instruction = task.get('instruction', task.get('description', ''))
    
    script_path = STATE_DIR / f"run_{task['task_id']}.sh"
    with open(script_path, "w") as f:
        f.write("#!/bin/bash\n" + instruction)
    os.chmod(script_path, 0o755)
    
    result = subprocess.run([str(script_path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    return {
        "status": "SUCCESS" if result.returncode == 0 else "FAILED",
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.returncode,
        "execution_mode": "NATIVE"
    }

def run_agy(task, config):
    write_log(f"Running AI task {task['task_id']} via agy")
    instruction = task.get('instruction', task.get('description', ''))
    
    prompt = f"Task ID: {task['task_id']}\nInstruction: {instruction}\n\nYou are a headless worker on Mac. You MUST execute the instruction. After you have successfully executed the instruction, you MUST output a final JSON object in a markdown codeblock. The JSON must contain a 'status' field set to 'SUCCESS' and a 'stdout_summary' field explaining what you did."
    
    agy_bin = shutil.which("agy") or shutil.which("agy", path=os.environ.get("PATH", "") + ":/Users/user/.local/bin:/usr/local/bin:/opt/homebrew/bin")
    if not agy_bin:
        return {"status": "FAILED", "reason": "AGY_NOT_FOUND", "execution_mode": "ANTIGRAVITY"}
        
    cmd = [agy_bin, "-p", prompt, "--dangerously-skip-permissions"]
    
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate(timeout=3600)
        
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
    write_log("Starting Mac Worker Daemon...")
    config = load_config()
    current_task_state_file = STATE_DIR / "current_task.json"
    
    if current_task_state_file.exists():
        write_log("Found unfinished task from previous run, resuming...")
        with open(current_task_state_file, 'r') as f:
            claimed_task = json.load(f)
        claimed_file = claimed_task['file']
        task = claimed_task['task']
    else:
        claimed_file, task = None, None
        
    while True:
        try:
            if not task:
                claimed_file, task = fetch_task_local(config)
                
            if task:
                if not current_task_state_file.exists():
                    with open(current_task_state_file, 'w') as f:
                        json.dump({'file': claimed_file, 'task': task}, f)
                        
                write_log(f"Processing task {task['task_id']}")
                mode = task.get("mode", "ANTIGRAVITY")
                if mode == "NATIVE":
                    res = run_native(task, config)
                else:
                    res = run_agy(task, config)
                
                res["goal_id"] = task.get("goal_id")
                res["task_id"] = task["task_id"]
                res["worker_id"] = config["WORKER_ID"]
                res["provider"] = "mac_" + res.get("execution_mode", "unknown").lower()
                res["run_id"] = str(uuid.uuid4())
                
                out_file = OUTBOX_DIR / f"{task['task_id']}_result.json"
                
                # Simulate backoff if network/directory unavailable
                retries = 0
                while retries < 5:
                    try:
                        with open(out_file, 'w') as f:
                            json.dump(res, f)
                        break
                    except Exception as we:
                        write_log(f"Failed to write result, backoff... {we}")
                        time.sleep(2 ** retries)
                        retries += 1
                        
                write_log(f"Result written to {out_file}")
                
                if os.path.exists(claimed_file):
                    os.remove(claimed_file)
                if current_task_state_file.exists():
                    os.remove(current_task_state_file)
                    
                task = None
                claimed_file = None
                
        except Exception as e:
            write_log(f"Error in poll loop: {e}\n{traceback.format_exc()}")
            
        time.sleep(config["POLL_INTERVAL_SECONDS"])

if __name__ == "__main__":
    loop()
