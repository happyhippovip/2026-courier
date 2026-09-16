import json, sys, os, time, subprocess, shutil
from pathlib import Path
import requests

def run_cmd(cmd):
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return result.returncode, result.stdout.strip(), result.stderr.strip()

def http_post_result(res):
    api_url = os.environ.get("COURIER_SERVER", "http://127.0.0.1:8080").rstrip("/")
    api_key = os.environ.get("COURIER_API_KEY")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        resp = requests.post(f"{api_url}/tasks/result", json=res, headers=headers)
        print(f"[GitHub Transport] HTTP Result POST response: {resp.status_code}")
    except Exception as e:
        print(f"[GitHub Transport] Failed to HTTP POST result: {e}")

def run(task_file):
    with open(task_file, 'r') as f:
        task = json.load(f)
        
    task_id = task.get('task_id')
    dispatch_id = task.get('dispatch_id')
    if not dispatch_id:
        print("[GitHub Transport] Missing dispatch_id in task packet.")
        sys.exit(1)
        
    payload = json.dumps(task)
    
    # Check for recovery
    print(f"[GitHub Transport] Checking for existing run with artifact result-{dispatch_id}...")
    rc, out, err = run_cmd(["gh", "run", "list", "--workflow=courier_worker.yml", "--json", "databaseId,status"])
    
    already_triggered = False
    if rc == 0:
        try:
            runs = json.loads(out)
            for r in runs:
                if r['status'] in ['completed', 'in_progress']:
                    rid = str(r['databaseId'])
                    rc_art, out_art, err_art = run_cmd(["gh", "api", f"/repos/happyhippovip/2026-courier/actions/runs/{rid}/artifacts"])
                    if rc_art == 0:
                        arts = json.loads(out_art).get("artifacts", [])
                        if any(a["name"] == f"result-{dispatch_id}" for a in arts):
                            print(f"[GitHub Transport] Found existing run {rid} for dispatch {dispatch_id}. Skipping trigger.")
                            already_triggered = True
                            break
        except Exception as e:
            pass
            
    if not already_triggered:
        print(f"[GitHub Transport] Routing task {task_id} to GitHub Actions...")
        cmd = [
            "gh", "workflow", "run", "courier_worker.yml",
            "-f", f"task_payload={payload}"
        ]
        rc, out, err = run_cmd(cmd)
        if rc != 0:
            print(f"[GitHub Transport] Failed to trigger workflow: {err}")
            res = {"status": "FAILED", "reason": "DISPATCH_FAILED", "task_id": task_id, "stderr": err, "dispatch_id": dispatch_id}
            http_post_result(res)
            return
        print(f"[GitHub Transport] Workflow triggered.")

    print(f"[GitHub Transport] Polling for exact artifact result-{dispatch_id}...")
    
    timeout = 300
    start = time.time()
    
    while time.time() - start < timeout:
        time.sleep(15)
        rc, out, err = run_cmd(["gh", "run", "list", "--workflow=courier_worker.yml", "--json", "databaseId,status"])
        if rc != 0: continue
            
        try:
            runs = json.loads(out)
        except:
            continue
            
        for r in runs:
            if r['status'] in ['completed', 'in_progress']:
                rid = str(r['databaseId'])
                dl_cmd = ["gh", "run", "download", rid, "-n", f"result-{dispatch_id}", "-D", f"tmp_artifact_{dispatch_id}"]
                rc_dl, out_dl, err_dl = run_cmd(dl_cmd)
                
                if rc_dl == 0:
                    print(f"[GitHub Transport] Exact artifact found in run {rid}!")
                    
                    tmp_dir = Path(f"tmp_artifact_{dispatch_id}")
                    result_json_path = tmp_dir / f"result_{dispatch_id}.json"
                    
                    if result_json_path.exists():
                        result_payload = json.loads(result_json_path.read_text(encoding="utf-8"))
                        http_post_result(result_payload)
                        
                        # Copy canary files to root so the verifier can see them locally
                        # Note: if verifier runs remotely, it needs them downloaded. We download them here.
                        for canary in tmp_dir.glob("courier_canary_*.txt"):
                            shutil.copy(canary, ".")
                            
                        shutil.rmtree(tmp_dir)
                        return
                    else:
                        print("[GitHub Transport] Missing result json in artifact!")
                        shutil.rmtree(tmp_dir)
        
    print(f"[GitHub Transport] Timeout waiting for task {task_id} (dispatch_id: {dispatch_id}).")
    res = {"status": "FAILED", "reason": "TIMEOUT", "task_id": task_id, "dispatch_id": dispatch_id}
    http_post_result(res)

if __name__ == "__main__":
    run(sys.argv[1])
