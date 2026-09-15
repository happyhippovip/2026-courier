import json, sys, os, time, subprocess, shutil
from pathlib import Path

def run_cmd(cmd):
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return result.returncode, result.stdout.strip(), result.stderr.strip()

def run(task_file):
    with open(task_file, 'r') as f:
        task = json.load(f)
        
    task_id = task.get('task_id')
    dispatch_id = task.get('dispatch_id')
    if not dispatch_id:
        print("[GitHub Transport] Missing dispatch_id in task packet.")
        sys.exit(1)
        
    payload = json.dumps(task)
    
    print(f"[GitHub Transport] Routing task {task_id} to GitHub Actions...")
    
    # Trigger workflow
    cmd = [
        "gh", "workflow", "run", "courier_worker.yml",
        "-f", f"task_payload={payload}"
    ]
    rc, out, err = run_cmd(cmd)
    if rc != 0:
        print(f"[GitHub Transport] Failed to trigger workflow: {err}")
        res = {"status": "FAILED", "reason": "DISPATCH_FAILED", "task_id": task_id, "stderr": err}
        os.makedirs("results/incoming", exist_ok=True)
        with open(f"results/incoming/{task_id}_result.json", 'w') as f:
            json.dump(res, f)
        return
        
    print(f"[GitHub Transport] Workflow triggered. Polling for exact artifact result-{dispatch_id}...")
    
    timeout = 300
    start = time.time()
    
    # We want to find the exact run containing an artifact named result-{dispatch_id}
    # To avoid polling all runs, we list runs created recently for courier_worker.yml
    run_id_found = None
    
    while time.time() - start < timeout:
        time.sleep(15)
        # Fetch latest runs
        rc, out, err = run_cmd(["gh", "run", "list", "--workflow=courier_worker.yml", "--json", "databaseId,status"])
        if rc != 0:
            continue
            
        try:
            runs = json.loads(out)
        except:
            continue
            
        for r in runs:
            if r['status'] in ['completed', 'in_progress']:
                rid = str(r['databaseId'])
                # Download artifact specifically named result-{dispatch_id}
                dl_cmd = ["gh", "run", "download", rid, "-n", f"result-{dispatch_id}", "-D", f"tmp_artifact_{dispatch_id}"]
                rc_dl, out_dl, err_dl = run_cmd(dl_cmd)
                
                if rc_dl == 0:
                    print(f"[GitHub Transport] Exact artifact found in run {rid}!")
                    run_id_found = rid
                    
                    tmp_dir = Path(f"tmp_artifact_{dispatch_id}")
                    result_json_path = tmp_dir / f"result_{dispatch_id}.json"
                    
                    if result_json_path.exists():
                        os.makedirs("results/incoming", exist_ok=True)
                        # We just copy the artifact to incoming results, but it must be named {task_id}_result.json so the server picks it up
                        result_payload = json.loads(result_json_path.read_text(encoding="utf-8"))
                        incoming = Path(f"results/incoming/{task_id}_result.json")
                        incoming_tmp = incoming.with_suffix(".json.tmp")
                        incoming_tmp.write_text(json.dumps(result_payload), encoding="utf-8")
                        os.replace(incoming_tmp, incoming)
                        
                        # Copy canary files to root
                        for canary in tmp_dir.glob("courier_canary_*.txt"):
                            shutil.copy(canary, ".")
                            
                        shutil.rmtree(tmp_dir)
                        return
                    else:
                        print("[GitHub Transport] Missing result json in artifact!")
                        shutil.rmtree(tmp_dir)
        
    print(f"[GitHub Transport] Timeout waiting for task {task_id} (dispatch_id: {dispatch_id}).")
    res = {"status": "FAILED", "reason": "TIMEOUT", "task_id": task_id, "dispatch_id": dispatch_id}
    os.makedirs("results/incoming", exist_ok=True)
    with open(f"results/incoming/{task_id}_result.json", 'w') as f:
        json.dump(res, f)

if __name__ == "__main__":
    run(sys.argv[1])
