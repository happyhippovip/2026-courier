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
    
    # Map Courier target to GitHub Runner labels
    target = task.get('target_capability', 'github')
    if target == 'windows_cloud':
        runner_label = '"windows-latest"'
    elif target == 'windows_desktop' or target == 'windows':
        runner_label = '["self-hosted", "Windows"]'
    elif target == 'mac':
        runner_label = '["self-hosted", "macOS"]'
    else:
        runner_label = '"ubuntu-latest"'
        
    mode = task.get('mode', 'ANTIGRAVITY')
    
    task_type = task.get('task_type', 'run_tests')
    
    print(f"[GitHub Transport] Routing task {task_id} to GitHub Actions ({runner_label})...")
    
    # Trigger workflow
    cmd = [
        "gh", "workflow", "run", "courier_worker.yml",
        "--ref", "courier/windows-phase-15-completion",
        "-f", f"task_id={task_id}",
        "-f", f"task_type={task_type}",
        "-f", f"instruction={instruction}",
        "-f", f"goal_id={goal_id}",
        "-f", f"runner_label={runner_label}",
        "-f", f"mode={mode}"
    ]
    rc, out, err = run_cmd(cmd)
    if rc != 0:
        print(f"[GitHub Transport] Failed to trigger workflow: {err}")
        res = {
            "status": "WAITING_FOR_WORKER", 
            "reason": "DISPATCH_FAILED", 
            "task_id": task_id, 
            "goal_id": goal_id,
            "worker_id": task.get("worker_id", ""),
            "run_id": "failed",
            "stderr": err
        }
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
                        # Bind the downloaded result to the observable GitHub run.
                        os.makedirs("results/incoming", exist_ok=True)
                        result_payload = json.loads(result_json_path.read_text(encoding="utf-8"))
                        result_payload["run_id"] = run_id
                        incoming = Path(f"results/incoming/{task_id}_result.json")
                        incoming_tmp = incoming.with_suffix(".json.tmp")
                        incoming_tmp.write_text(json.dumps(result_payload), encoding="utf-8")
                        os.replace(incoming_tmp, incoming)
                        
                        # Also copy any canary files to workspace root for verification
                        for canary in tmp_dir.glob("courier_canary_*.txt"):
                            shutil.copy(canary, ".")
                            
                        # Clean up
                        shutil.rmtree(tmp_dir)
                        return
                    else:
                        shutil.rmtree(tmp_dir)
        
    print(f"[GitHub Transport] Timeout waiting for task {task_id}.")
    res = {
        "status": "WAITING_FOR_WORKER", 
        "reason": "TIMEOUT", 
        "task_id": task_id,
        "goal_id": goal_id,
        "worker_id": task.get("worker_id", ""),
        "run_id": "timeout"
    }
    os.makedirs("results/incoming", exist_ok=True)
    with open(f"results/incoming/{task_id}_result.json", 'w') as f:
        json.dump(res, f)

if __name__ == "__main__":
    run(sys.argv[1])
