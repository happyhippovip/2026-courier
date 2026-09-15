import json, sys, os, subprocess, uuid

def run(task_file):
    with open(task_file, 'r') as f:
        task = json.load(f)
        
    print(f"[Mac Worker] Executing task {task['task_id']} via Antigravity headless CLI...")
    prompt = f"Task: {task['task_id']}\nInstruction: {task['description']}\nReturn ONLY a valid JSON object in a markdown codeblock with a 'status' string field set to 'SUCCESS' and 'stdout_summary' summarizing what you did."
    
    cmd = [
        "agy", 
        "-p", prompt,
        "--disable-slash-commands" 
    ]
    
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = process.communicate(timeout=120)
    out = stdout.strip()
    
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
    
    res_json["goal_id"] = task.get("goal_id")
    res_json["task_id"] = task["task_id"]
    res_json["worker_id"] = "MAC-AGY-01"
    res_json["provider"] = "antigravity"
    res_json["run_id"] = str(process.pid)
    
    if not parsed and res_json.get("status") == "SUCCESS":
        res_json["status"] = "FAILED"
        
    os.makedirs("results/incoming", exist_ok=True)
    with open(f"results/incoming/{task['task_id']}_result.json", 'w') as f:
        json.dump(res_json, f)

if __name__ == "__main__":
    run(sys.argv[1])
