import json, time, os, sys, shutil, subprocess, glob
from pathlib import Path

def load_config():
    config_path = Path(__file__).parent / "config.json"
    with open(config_path, "r") as f:
        return json.load(f)

def run_task(task, config):
    print(f"[{config['WORKER_ID']}] Running task {task['task_id']}...")
    run_id = str(os.getpid())
    out_clean = ""
    stderr = ""
    returncode = 0
    
    # We execute powershell natively if it's a native capability test, 
    # otherwise we would use agy without global bypass.
    # For Vollautomatik Canary, the worker performs what is explicitly requested.
    instruction = task.get("description", "")
    
    try:
        if "native" in instruction.lower() or "canary" in instruction.lower():
            print(f"[{config['WORKER_ID']}] Executing native powershell task...")
            # Perform native work as requested by canary, explicitly reporting what executed
            canary_file = f"courier_canary_{task['task_id']}.txt"
            cmd = ["powershell", "-Command", f"Set-Content -Path {canary_file} -Value 'SUCCESS'"]
            process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
            returncode = process.returncode
            stderr = process.stderr
            out_clean = json.dumps({
                "status": "SUCCESS" if returncode == 0 else "FAILED",
                "stdout_summary": f"Native execution of '{' '.join(cmd)}' returned {returncode}",
                "stdout": process.stdout
            })
        else:
            print(f"[{config['WORKER_ID']}] 'agy' execution requested.")
            prompt = f"Task ID: {task['task_id']}\nInstruction: {instruction}\nOutput a markdown JSON block with status and stdout_summary."
            cmd = ["agy", "-p", prompt] # NO global danger bypass
            process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3600)
            returncode = process.returncode
            stderr = process.stderr
            out_clean = process.stdout.strip()
    except Exception as e:
        stderr = str(e)
        returncode = -1
            
    # Extract JSON
    parsed = False
    if "```json" in out_clean:
        ext = out_clean.split("```json")[1].split("```")[0].strip()
    elif "```" in out_clean:
        ext = out_clean.split("```")[1].split("```")[0].strip()
    else:
        ext = out_clean
        
    try:
        res_json = json.loads(ext)
        parsed = True
    except Exception:
        status = "FAILED"
        reason = "INVALID_RESULT"
        if returncode != 0:
            status = "FAILED"
            reason = "EXECUTION_ERROR"
        res_json = {
            "status": status,
            "reason": reason,
            "raw_diagnostic": out_clean,
            "stderr": stderr
        }
        
    res_json["goal_id"] = task.get("goal_id")
    res_json["task_id"] = task["task_id"]
    res_json["worker_id"] = config["WORKER_ID"]
    res_json["provider"] = "windows_native"
    res_json["run_id"] = run_id
    
    if not parsed and res_json.get("status") == "SUCCESS":
        res_json["status"] = "FAILED"
        
    return res_json

def loop():
    pid_file = Path(__file__).parent / "daemon.pid"
    if pid_file.exists():
        try:
            with open(pid_file, "r") as f:
                old_pid = int(f.read().strip())
            os.kill(old_pid, 0)
            print(f"Daemon already running with PID {old_pid}. Exiting.")
            sys.exit(0)
        except (OSError, ValueError):
            pid_file.unlink(missing_ok=True)
            
    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))

    config = load_config()
    inbox = Path(__file__).parent / config["WORKER_INBOX"]
    outbox = Path(__file__).parent / config["WORKER_OUTBOX"]
    
    print(f"[{config['WORKER_ID']}] Windows Worker Daemon started.")
    print(f"[{config['WORKER_ID']}] Polling {inbox} every {config['POLL_INTERVAL_SECONDS']}s...")
    
    while True:
        try:
            for claimed_file in glob.glob(str(inbox / "*.claimed")):
                claimed_path = Path(claimed_file)
                if time.time() - claimed_path.stat().st_mtime > 60: 
                    print(f"[{config['WORKER_ID']}] Recovering orphaned task {claimed_path.name}")
                    try:
                        os.rename(claimed_file, claimed_file.replace(".claimed", ""))
                    except OSError:
                        pass
                        
            for task_file in glob.glob(str(inbox / "*.json")):
                if task_file.endswith(".claimed"): continue
                
                claimed_file = task_file + ".claimed"
                try:
                    os.rename(task_file, claimed_file)
                except OSError:
                    continue 
                
                with open(claimed_file, 'r') as f:
                    task = json.load(f)
                
                out_file = outbox / f"{task['task_id']}_result.json"
                if out_file.exists():
                    os.remove(claimed_file)
                    continue
                
                res = run_task(task, config)
                
                with open(out_file, 'w') as f:
                    json.dump(res, f)
                    
                os.remove(claimed_file)
                print(f"[{config['WORKER_ID']}] Task {task['task_id']} completed.")
                
        except Exception as e:
            print(f"[{config['WORKER_ID']}] Error in poll loop: {e}")
            
        time.sleep(config["POLL_INTERVAL_SECONDS"])

if __name__ == "__main__":
    loop()
