import json, sys, os, subprocess

def run(task_file):
    with open(task_file, 'r') as f:
        task = json.load(f)
        
    print(f"[Mac Worker] Executing task {task['task_id']} via Antigravity headless CLI...")
    expected_artifact = f"courier_canary_{task['task_id']}.txt"
    
    prompt = f"Task ID: {task['task_id']}\nInstruction: {task['description']}\n\nYou are a headless worker. IMPORTANT: You MUST physically execute the following observable effect using your tools: Create a file named '{expected_artifact}' containing the text 'SUCCESS'.\nAfter you have successfully executed the instruction and created the file, you MUST output a final JSON object in a markdown codeblock. The JSON must contain a 'status' field set to 'SUCCESS' and a 'stdout_summary' field explaining what you did. Do NOT just output the JSON without doing the work!"
    
    cmd = [
        "agy", 
        "-p", prompt,
        "--dangerously-skip-permissions"
    ]
    
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = process.communicate(timeout=180)
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
