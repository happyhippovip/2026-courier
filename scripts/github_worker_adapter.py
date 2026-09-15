import json, sys, os, time, subprocess, shutil
from pathlib import Path

def run_cmd(cmd):
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return result.returncode, result.stdout.strip(), result.stderr.strip()

def run(task_file):
    with open(task_file, 'r') as f:
        task = json.load(f)
        
    task_id = task['task_id']
    goal_id = task.get('goal_id', '')
    instruction = task['description'] if 'description' in task else task.get('instruction', '')
    
    print(f"[GitHub Transport] Routing task {task_id} to GitHub Actions...")
    
    # Trigger workflow
    cmd = [
        "gh", "workflow", "run", "courier_worker.yml",
        "-f", f"task_id={task_id}",
        "-f", f"instruction={instruction}",
        "-f", f"goal_id={goal_id}"
    ]
    rc, out, err = run_cmd(cmd)
    if rc != 0:
        print(f"[GitHub Transport] Failed to trigger workflow: {err}")
        res = {"status": "FAILED", "reason": "DISPATCH_FAILED", "task_id": task_id, "stderr": err}
        os.makedirs("results/incoming", exist_ok=True)
        with open(f"results/incoming/{task_id}_result.json", 'w') as f:
            json.dump(res, f)
        return
        
    print(f"[GitHub Transport] Workflow triggered. Polling for artifact...")
    
    # Poll for completion. To avoid spamming, we list runs matching this workflow.
    # It takes time for the run to appear, then finish.
    timeout = 600
    start = time.time()
    
    while time.time() - start < timeout:
        time.sleep(15)
        # Check latest runs
        rc, out, err = run_cmd(["gh", "run", "list", "--workflow=courier_worker.yml", "--json", "databaseId,status,conclusion"])
        if rc != 0:
            continue
            
        try:
            runs = json.loads(out)
        except:
            continue
            
        for r in runs:
            # We can only check if the artifact exists for completed runs because we don't know the exact run ID easily without matching inputs.
            if r['status'] == 'completed':
                run_id = str(r['databaseId'])
                # Try to download artifact named courier-result-{task_id}
                dl_cmd = ["gh", "run", "download", run_id, "-n", f"courier-result-{task_id}", "-D", f"tmp_artifact_{task_id}"]
                rc_dl, out_dl, err_dl = run_cmd(dl_cmd)
                if rc_dl == 0:
                    print(f"[GitHub Transport] Downloaded artifact from run {run_id}!")
                    # Check what we downloaded
                    tmp_dir = Path(f"tmp_artifact_{task_id}")
                    result_json_path = tmp_dir / "result.json"
                    
                    if result_json_path.exists():
                        # Copy result JSON
                        os.makedirs("results/incoming", exist_ok=True)
                        shutil.copy(result_json_path, f"results/incoming/{task_id}_result.json")
                        
                        # Also copy any canary files to workspace root for verification
                        for canary in tmp_dir.glob("courier_canary_*.txt"):
                            shutil.copy(canary, ".")
                            
                        # Clean up
                        shutil.rmtree(tmp_dir)
                        return
                    else:
                        shutil.rmtree(tmp_dir)
        
    print(f"[GitHub Transport] Timeout waiting for task {task_id}.")
    res = {"status": "FAILED", "reason": "TIMEOUT", "task_id": task_id}
    os.makedirs("results/incoming", exist_ok=True)
    with open(f"results/incoming/{task_id}_result.json", 'w') as f:
        json.dump(res, f)

if __name__ == "__main__":
    run(sys.argv[1])
