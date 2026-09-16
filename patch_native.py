import re

with open("scripts/mac_worker/daemon.py", "r") as f:
    c = f.read()

run_native_new = """def run_native(task, config):
    import signal, os, subprocess, json
    write_log(f"Running NATIVE task {task['task_id']}")
    instruction = task.get('instruction', task.get('description', ''))
    
    action = extract_intent(instruction)
    pid_file = STATE_DIR / "current_task_pid.json"
    process = None
    try:
        if action == "echo":
            process = subprocess.Popen(instruction, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, executable="/bin/bash", preexec_fn=os.setsid)
        elif action == "git_status":
            process = subprocess.Popen(["git", "status"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, preexec_fn=os.setsid)
        else:
            return {"status": "FAILED", "stderr": f"Action '{action}' is allowed but handler is not implemented yet.", "execution_mode": "NATIVE"}
            
        with open(pid_file, "w") as f:
            json.dump({"pid": process.pid, "pgid": os.getpgid(process.pid)}, f)
            
        stdout, stderr = process.communicate(timeout=300)
        
        if pid_file.exists():
            os.remove(pid_file)
            
        return {
            "status": "SUCCESS" if process.returncode == 0 else "FAILED",
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": process.returncode,
            "execution_mode": "NATIVE"
        }
    except subprocess.TimeoutExpired as e:
        write_log(f"Task {task['task_id']} timed out. Cleaning up exact process group.")
        if process:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except:
                pass
        if pid_file.exists():
            os.remove(pid_file)
        return {"status": "FAILED", "stderr": "TimeoutExpired - Process killed.", "execution_mode": "NATIVE"}
    except Exception as e:
        if process:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except:
                pass
        if pid_file.exists():
            os.remove(pid_file)
        return {"status": "FAILED", "stderr": str(e), "execution_mode": "NATIVE"}
"""

c = re.sub(r'def run_native\(task, config\):.*?def run_agy', run_native_new + '\ndef run_agy', c, flags=re.DOTALL)

with open("scripts/mac_worker/daemon.py", "w") as f:
    f.write(c)
