import os, sys, time, subprocess, json, urllib.request, urllib.error
from pathlib import Path

def run_proof():
    os.environ["COURIER_STATE_FILE"] = os.path.abspath("test_central_state.json")
    if os.path.exists("test_central_state.json"):
        os.remove("test_central_state.json")
    if os.path.exists("server/state/central_state.json"):
        os.remove("server/state/central_state.json")
        
    os.environ["COURIER_API_KEY"] = "test-secret-key"
    os.environ["COURIER_WORKER_ID"] = "w22-worker"
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

    # Register worker first so claim_task works
    print("Registering worker...")
    req = urllib.request.Request("http://127.0.0.1:8080/workers/register",
                                 data=json.dumps({"worker_id": "w22-worker", "capabilities": ["windows"]}).encode(),
                                 headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                 method="POST")
    urllib.request.urlopen(req)

    print("Submitting goal with 2 parallel tasks...")
    plan = [
        {"task_id": "T-W22-1", "instruction": "echo 'Wait task'", "target_agent": "windows"},
        {"task_id": "T-W22-2", "instruction": "echo 'W22 test' > w22_artifact.txt", "target_agent": "windows", "artifacts": ["w22_artifact.txt"]}
    ]
    req = urllib.request.Request("http://127.0.0.1:8080/goals", 
                                 data=json.dumps({"goal_text": "Verify W22", "workflow_plan": plan, "terminal": True}).encode(), 
                                 headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req) as res:
        goal_data = json.loads(res.read())
        goal_id = goal_data["goal_id"]

    print("Simulating worker claim for Task 1...")
    req = urllib.request.Request("http://127.0.0.1:8080/tasks/claim",
                                 data=json.dumps({"worker_id": "w22-worker"}).encode(),
                                 headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req) as res:
        claim_data = json.loads(res.read())
        task1 = claim_data.get("task")
        if not task1 or task1["task_id"] != "T-W22-1":
            print(f"Failed to claim T-W22-1. Got: {claim_data}")
            sys.exit(1)

    print("Setting Task 1 to WAITING_PROVIDER...")
    req = urllib.request.Request(f"http://127.0.0.1:8080/tasks/{task1['task_id']}/provider_wait",
                                 data=json.dumps({"worker_id": "w22-worker", "wait_type": "WAITING_PROVIDER", "reason": "Test"}).encode(),
                                 headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                 method="POST")
    urllib.request.urlopen(req)

    marker = Path("scripts/windows_worker/state/result_marker.json")
    if marker.exists(): marker.unlink()
    
    print("Starting Windows Worker daemon.py to process Task 2...")
    worker_proc = subprocess.Popen([sys.executable, "scripts/windows_worker/daemon.py"], env=os.environ)
    
    recovered = False
    
    for _ in range(120):
        req = urllib.request.Request(f"http://127.0.0.1:8080/goals/{goal_id}", headers={"Authorization": "Bearer test-secret-key"})
        goal_state = json.loads(urllib.request.urlopen(req).read())
        
        # Check task 2
        tasks = goal_state.get("tasks", [])
        t2 = next((t for t in tasks if t["task_id"] == "T-W22-2"), None)
        if t2:
            print(f"T-W22-2 status: {t2['status']}", flush=True)
            if t2["status"] in ("RESULT_RECEIVED", "RECONCILED", "RECONCILED_PENDING_MERGE"):
                recovered = True
                break
            if t2["status"] == "FAILED_TERMINAL" or t2["status"] == "FAILED":
                print(f"T-W22-2 failed: {t2}")
                break
        time.sleep(1)

    worker_proc.kill()
    server_proc.kill()
    
    if not recovered:
        sys.exit("W22 Proof Failed: Task 2 was blocked by Task 1's WAITING_PROVIDER state.")
        
    print("PASS_W22: PROVIDER_WAIT_ISOLATION")

if __name__ == "__main__":
    run_proof()
