import os, sys, time, subprocess, json, urllib.request, urllib.error
from pathlib import Path

def run_proof():
    os.environ["COURIER_STATE_FILE"] = os.path.abspath("test_central_state.json")
    if os.path.exists("test_central_state.json"):
        os.remove("test_central_state.json")
    if os.path.exists("server/state/central_state.json"):
        os.remove("server/state/central_state.json")
        
    os.environ["COURIER_API_KEY"] = "test-secret-key"
    os.environ["COURIER_WORKER_ID"] = "w23-worker"
    os.environ["UV_PROJECT_ENVIRONMENT"] = os.path.abspath(".venv_service")
    
    print("Starting Courier Server...")
    server_proc = subprocess.Popen([sys.executable, "-m", "flask", "--app", "server.app:app", "run", "--port", "8080"], env=os.environ)
    
    def wait_for_port(port):
        for _ in range(30):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/health")
                break
            except Exception:
                time.sleep(0.5)
        else:
            sys.exit(f"Port {port} failed to start")
            
    wait_for_port(8080)

    print("Registering worker...")
    req = urllib.request.Request("http://127.0.0.1:8080/workers/register",
                                 data=json.dumps({"worker_id": "w23-worker", "capabilities": ["windows"]}).encode(),
                                 headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                 method="POST")
    urllib.request.urlopen(req)

    print("Submitting goal...")
    plan = [
        {"task_id": "T-W23", "instruction": "echo 'W23 test' > w23_artifact.txt", "target_agent": "windows", "artifacts": ["w23_artifact.txt"]}
    ]
    req = urllib.request.Request("http://127.0.0.1:8080/goals", 
                                 data=json.dumps({"goal_text": "Verify W23", "workflow_plan": plan, "terminal": True}).encode(), 
                                 headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req) as res:
        goal_data = json.loads(res.read())
        goal_id = goal_data["goal_id"]

    print("Simulating worker claim...")
    req = urllib.request.Request("http://127.0.0.1:8080/tasks/claim",
                                 data=json.dumps({"worker_id": "w23-worker"}).encode(),
                                 headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req) as res:
        claim_data = json.loads(res.read())
        task1 = claim_data.get("task")
        if not task1 or task1["task_id"] != "T-W23":
            sys.exit(f"Failed to claim T-W23. Got: {claim_data}")

    print("Setting Task to WAITING_PROVIDER...")
    req = urllib.request.Request(f"http://127.0.0.1:8080/tasks/{task1['task_id']}/provider_wait",
                                 data=json.dumps({"worker_id": "w23-worker", "wait_type": "WAITING_PROVIDER", "reason": "Test"}).encode(),
                                 headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                 method="POST")
    urllib.request.urlopen(req)

    print("Resuming Task...")
    req = urllib.request.Request(f"http://127.0.0.1:8080/tasks/{task1['task_id']}/resume",
                                 data=json.dumps({"action": "retry"}).encode(),
                                 headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                 method="POST")
    urllib.request.urlopen(req)

    marker = Path("scripts/windows_worker/state/result_marker.json")
    if marker.exists(): marker.unlink()
    
    print("Starting Windows Worker daemon.py to reclaim and process Task...")
    worker_proc = subprocess.Popen([sys.executable, "scripts/windows_worker/daemon.py"], env=os.environ)
    
    recovered = False
    
    for _ in range(120):
        req = urllib.request.Request(f"http://127.0.0.1:8080/goals/{goal_id}", headers={"Authorization": "Bearer test-secret-key"})
        goal_state = json.loads(urllib.request.urlopen(req).read())
        
        tasks = goal_state.get("tasks", [])
        t = next((t for t in tasks if t["task_id"] == "T-W23"), None)
        if t:
            print(f"T-W23 status: {t['status']}, attempts: {t.get('attempts')}", flush=True)
            if t["status"] in ("RESULT_RECEIVED", "RECONCILED", "RECONCILED_PENDING_MERGE"):
                if t.get("attempts", 0) == 1:
                    recovered = True
                else:
                    print(f"Failed: Attempts was {t.get('attempts')}, expected 1")
                break
            if t["status"] == "FAILED_TERMINAL" or t["status"] == "FAILED":
                print(f"T-W23 failed: {t}")
                break
        time.sleep(1)

    worker_proc.kill()
    server_proc.kill()
    
    if not recovered:
        sys.exit("W23 Proof Failed: Task was not correctly recovered with attempts=1.")
        
    print("PASS_W23: PROVIDER_RESUME_SAME_SAFE_ATTEMPT")

if __name__ == "__main__":
    run_proof()
