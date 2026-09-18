import os, sys, time, subprocess, json, urllib.request, urllib.error
from pathlib import Path

def run_proof():
    os.environ["COURIER_STATE_FILE"] = os.path.abspath("test_central_state.json")
    if os.path.exists("test_central_state.json"):
        os.remove("test_central_state.json")
    if os.path.exists("server/state/central_state.json"):
        os.remove("server/state/central_state.json")
        
    os.environ["COURIER_API_KEY"] = "test-secret-key"
    os.environ["COURIER_WORKER_ID"] = "w24-worker"
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
                                 data=json.dumps({"worker_id": "w24-worker", "capabilities": ["windows"]}).encode(),
                                 headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                 method="POST")
    urllib.request.urlopen(req)

    print("Submitting goal...")
    plan = [
        {"task_id": "T-W24", "instruction": "echo 'W24 test'", "target_agent": "windows"}
    ]
    req = urllib.request.Request("http://127.0.0.1:8080/goals", 
                                 data=json.dumps({"goal_text": "Verify W24", "workflow_plan": plan, "terminal": True}).encode(), 
                                 headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req) as res:
        goal_data = json.loads(res.read())
        goal_id = goal_data["goal_id"]

    print("Simulating worker claim...")
    req = urllib.request.Request("http://127.0.0.1:8080/tasks/claim",
                                 data=json.dumps({"worker_id": "w24-worker"}).encode(),
                                 headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req) as res:
        claim_data = json.loads(res.read())
        task1 = claim_data.get("task")
        if not task1 or task1["task_id"] != "T-W24":
            sys.exit(f"Failed to claim T-W24. Got: {claim_data}")
            
    print("Simulating ambiguous crash result...")
    result_data = {
        "status": "FAILED",
        "stdout": "",
        "stderr": "AMBIGUOUS_CRASH during external API call",
        "goal_id": goal_id,
        "task_id": task1["task_id"],
        "attempt_id": task1["attempt_id"],
        "dispatch_id": task1["dispatch_id"],
        "execution_ref": task1["execution_ref"],
        "worker_id": "w24-worker",
        "provider": "windows_native",
        "run_id": "test",
        "result_id": "res-123",
        "artifacts": []
    }
    
    req = urllib.request.Request("http://127.0.0.1:8080/tasks/result",
                                 data=json.dumps(result_data).encode(),
                                 headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                 method="POST")
    urllib.request.urlopen(req)
    
    recovered = False
    print("Checking goal state...")
    
    for _ in range(10):
        req = urllib.request.Request(f"http://127.0.0.1:8080/goals/{goal_id}", headers={"Authorization": "Bearer test-secret-key"})
        goal_state = json.loads(urllib.request.urlopen(req).read())
        
        tasks = goal_state.get("tasks", [])
        t = next((t for t in tasks if t["task_id"] == "T-W24"), None)
        if t:
            print(f"T-W24 status: {t['status']}", flush=True)
            if t["status"] == "HUMAN_REQUIRED" and t.get("recovery_reason") == "AMBIGUOUS_EFFECT_CRASH":
                recovered = True
                break
        time.sleep(0.5)

    server_proc.kill()
    
    if not recovered:
        sys.exit("W24 Proof Failed: Task did not quarantine to HUMAN_REQUIRED correctly.")
        
    print("PASS_W24: AMBIGUOUS_EXTERNAL_EFFECT_FAIL_CLOSED")

if __name__ == "__main__":
    run_proof()
