import os, sys, time, subprocess, json, urllib.request, urllib.error
import shutil
from pathlib import Path

def run_proof():
    os.environ["COURIER_STATE_FILE"] = os.path.abspath("test_central_state.json")
    if os.path.exists("test_central_state.json"):
        os.remove("test_central_state.json")
    if os.path.exists("server/state/central_state.json"):
        os.remove("server/state/central_state.json")
        
    os.environ["COURIER_API_KEY"] = "test-secret-key"
    os.environ["COURIER_WORKER_ID"] = "w20-worker"
    os.environ["UV_PROJECT_ENVIRONMENT"] = os.path.abspath(".venv_service")

    print("Starting Courier Server...")
    server_proc = subprocess.Popen([sys.executable, "-m", "flask", "--app", "server.app:app", "run", "--port", "8080"], env=os.environ)
    
    for _ in range(30):
        try:
            req = urllib.request.Request("http://127.0.0.1:8080/health")
            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    break
        except Exception:
            time.sleep(0.5)
    else:
        server_proc.kill()
        sys.exit("Server failed to start")

    print("Submitting goal...")
    plan = [{"task_id": "T-W20", "instruction": "echo 'W20 test'", "target_agent": "windows"}]
    req = urllib.request.Request("http://127.0.0.1:8080/goals", 
                                 data=json.dumps({"goal_text": "Verify W20", "workflow_plan": plan, "terminal": True}).encode(), 
                                 headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                 method="POST")
    try:
        with urllib.request.urlopen(req) as res:
            goal_data = json.loads(res.read())
            goal_id = goal_data["goal_id"]
    except Exception as e:
        server_proc.kill()
        sys.exit(f"Goal submission failed: {e}")

    print("Claiming task manually to get task metadata...")
    req = urllib.request.Request("http://127.0.0.1:8080/workers/register",
                                 data=json.dumps({"worker_id": "w20-worker", "capabilities": ["windows"]}).encode(),
                                 headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                 method="POST")
    urllib.request.urlopen(req).read()
    
    req = urllib.request.Request("http://127.0.0.1:8080/tasks/claim",
                                 data=json.dumps({"worker_id": "w20-worker"}).encode(),
                                 headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                 method="POST")
    res = urllib.request.urlopen(req)
    task_data = json.loads(res.read())
    print("Claim response:", task_data)
    task = task_data["task"]
    
    print("Writing result_marker.json to simulate crash after completion but before ACK...")
    worker_state_dir = Path("scripts/windows_worker/state")
    worker_state_dir.mkdir(parents=True, exist_ok=True)
    marker_path = worker_state_dir / "result_marker.json"
    
    crashed_result = {
        "status": "SUCCESS",
        "stdout": "W20 simulated recovery output",
        "stderr": "",
        "goal_id": goal_id,
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "execution_ref": task["execution_ref"],
        "worker_id": "w20-worker",
        "provider": "windows_native",
        "run_id": "w20-run",
        "result_id": "res-w20-test",
        "artifacts": [
            {
                "path": f"courier_canary_{task['task_id']}.txt",
                "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
            }
        ]
    }
    with open(marker_path, "w") as f:
        json.dump(crashed_result, f)
        
    print("Starting Windows Worker daemon.py...")
    worker_proc = subprocess.Popen([sys.executable, "scripts/windows_worker/daemon.py"], env=os.environ)
    
    # Wait for the worker to report the result and the task to become RESULT_RECEIVED
    recovered = False
    for _ in range(30):
        req = urllib.request.Request(f"http://127.0.0.1:8080/goals/{goal_id}", headers={"Authorization": "Bearer test-secret-key"})
        goal_state = json.loads(urllib.request.urlopen(req).read())
        task_state = goal_state["tasks"][0]
        if task_state["status"] == "RESULT_RECEIVED":
            print(f"Task is RESULT_RECEIVED with result_id: {task_state.get('result', {}).get('result_id')}")
            if task_state.get("result", {}).get("result_id") == "res-w20-test":
                recovered = True
                break
        time.sleep(0.5)

    worker_proc.kill()
    server_proc.kill()
    
    if not recovered:
        sys.exit("W20 Proof Failed: Task result was not recovered and delivered by worker startup check.")
        
    if marker_path.exists():
        sys.exit("W20 Proof Failed: result_marker.json was not unlinked after successful recovery.")
        
    print("PASS_W20: RESULT_DURABILITY_BEFORE_ACK")

if __name__ == "__main__":
    run_proof()
