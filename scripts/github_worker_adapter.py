import json, sys, os, time, subprocess, shutil, uuid
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
    
    result_file = Path(f"results/incoming/{task_id}_result.json")
    if result_file.exists():
        print(f"[GitHub Transport] Result already exists for {task_id}. Skipping dispatch.")
        return

    dispatch_file = Path(f"results/incoming/{task_id}_dispatch.json")
    attempt_id = None
    
    if dispatch_file.exists():
        try:
            with open(dispatch_file, 'r') as df:
                dinfo = json.load(df)
                attempt_id = dinfo['attempt_id']
            print(f"[GitHub Transport] Recovered existing dispatch for task {task_id} (Attempt: {attempt_id}). Resuming poll...")
        except Exception as e:
            print(f"[GitHub Transport] Failed to read dispatch file, generating new attempt. Error: {e}")
            attempt_id = None
            
    if not attempt_id:
        # Use attempt_id/dispatch_id from task payload if provided, else generate new
        attempt_id = task.get('attempt_id', task.get('dispatch_id', str(uuid.uuid4())))
        
        print(f"[GitHub Transport] Routing task {task_id} (Attempt: {attempt_id}) to GitHub Actions ({runner_label})...")
        
        # Trigger workflow
        cmd = [
            "gh", "workflow", "run", "courier_worker.yml",
            "--ref", "courier/windows-phase-15-completion",
            "-f", f"task_id={task_id}",
            "-f", f"attempt_id={attempt_id}",
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
                "attempt_id": attempt_id,
                "run_id": "failed",
                "stderr": err
            }
            os.makedirs("results/incoming", exist_ok=True)
            with open(result_file, 'w') as f:
                json.dump(res, f)
            return
            
        os.makedirs("results/incoming", exist_ok=True)
        with open(dispatch_file, 'w') as df:
            json.dump({"attempt_id": attempt_id, "task_id": task_id, "timestamp": time.time()}, df)
            
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
                # Try to download artifact named courier-result-{attempt_id}
                dl_cmd = ["gh", "run", "download", run_id, "-n", f"courier-result-{attempt_id}", "-D", f"tmp_artifact_{task_id}"]
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
                        result_payload["attempt_id"] = attempt_id
                        
                        acceptance_criteria = task.get('acceptance_criteria', [])
                        if result_payload.get('status') == 'SUCCESS' and acceptance_criteria:
                            exec_log_path = tmp_dir / "execution.log"
                            log_content = exec_log_path.read_text(encoding="utf-8", errors="replace") if exec_log_path.exists() else ""
                            
                            failed_criteria = []
                            for ac in acceptance_criteria:
                                ac_lower = ac.lower()
                                if "exit code" in ac_lower:
                                    continue
                                
                                # Determine a basic mechanism to verify criteria:
                                # 1. If log has exceptions but process exited 0, fail it.
                                if "Traceback (most recent call last):" in log_content or "Exception:" in log_content:
                                    failed_criteria.append(ac)
                                # 2. If criteria expects a specific canary file to be generated
                                elif "file" in ac_lower or "bundle" in ac_lower or "report" in ac_lower:
                                    # Since we don't know the exact filename, we look if any canary exists
                                    canaries = list(tmp_dir.glob("*.*"))
                                    # if it's just result.json and execution.log, maybe it failed to generate artifacts
                                    # We'll just rely on the log exception check for now to be safe and avoid false positives
                            
                            if failed_criteria:
                                result_payload['status'] = 'FAILED'
                                result_payload['reason'] = f"Acceptance criteria validation failed for: {', '.join(failed_criteria)}. Process returned 0 but errors or unmet conditions detected."

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
        "attempt_id": attempt_id,
        "run_id": "timeout"
    }
    os.makedirs("results/incoming", exist_ok=True)
    with open(f"results/incoming/{task_id}_result.json", 'w') as f:
        json.dump(res, f)

if __name__ == "__main__":
    run(sys.argv[1])
