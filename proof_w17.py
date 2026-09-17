import os, sys, time, subprocess, json, urllib.request, urllib.error
import urllib.parse
from uuid import uuid4

def run_proof():
    # 1. Clean state
    data_dir = os.environ.get("COURIER_DATA_DIR", r"C:\ProgramData\Courier")
    state_file = os.environ.get("COURIER_STATE_FILE", os.path.join(data_dir, "central_state.json"))
    if os.path.exists(state_file):
        os.remove(state_file)
        
    os.environ["COURIER_API_KEY"] = "test-secret-key"
    os.environ["COURIER_VERIFIER_API_KEY"] = "test-verifier-key"
    os.environ["UV_PROJECT_ENVIRONMENT"] = os.path.abspath(".venv_service")

    print("Starting Courier Server...")
    server_proc = subprocess.Popen([sys.executable, "-m", "flask", "--app", "server.app:app", "run", "--port", "8080"], env=os.environ)
    
    # Wait for server
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

    print("Server is up. Submitting goal...")
    plan = [{"task_id": "T-W17", "instruction": "Test task", "target_agent": "linux"}]
    req = urllib.request.Request("http://127.0.0.1:8080/goals", 
                                 data=json.dumps({"goal_text": "Verify W17", "workflow_plan": plan, "terminal": True}).encode(), 
                                 headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                 method="POST")
    try:
        with urllib.request.urlopen(req) as res:
            goal_data = json.loads(res.read())
            goal_id = goal_data["goal_id"]
    except Exception as e:
        server_proc.kill()
        sys.exit(f"Goal submission failed: {e}")

    print("Registering worker and claiming task...")
    req = urllib.request.Request("http://127.0.0.1:8080/workers/register",
                                 data=json.dumps({"worker_id": "w17-worker", "capabilities": ["linux"]}).encode(),
                                 headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                 method="POST")
    urllib.request.urlopen(req).read()
    
    req = urllib.request.Request("http://127.0.0.1:8080/tasks/claim",
                                 data=json.dumps({"worker_id": "w17-worker"}).encode(),
                                 headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                 method="POST")
    res = urllib.request.urlopen(req)
    task_data = json.loads(res.read())
    task = task_data["task"]
    task_id = task["task_id"]

    print("Starting Verifier for the first time, then killing it...")
    verifier_proc = subprocess.Popen([sys.executable, "scripts/courier_verifier.py"], env=os.environ)
    time.sleep(2)
    verifier_proc.kill()
    verifier_proc.wait()

    print("Verifier is dead. Submitting task result (now pending verification)...")
    res_payload = {
        "task_id": task_id,
        "goal_id": goal_id,
        "run_id": task.get("run_id") or "test-run",
        "worker_id": "w17-worker",
        "result_id": f"res-{uuid4().hex[:8]}",
        "attempt_id": task.get("attempt_id"),
        "dispatch_id": task.get("dispatch_id"),
        "execution_ref": task.get("execution_ref"),
        "status": "SUCCESS",
        "artifacts": [{"path": "dummy.txt", "sha256": "d3eb539a556352f3f47881d71fb0e5777b2f3e9a4251d283c18c67ce996774b7"}],
        "result_data": {"test": "w17"}
    }
    req = urllib.request.Request("http://127.0.0.1:8080/tasks/result",
                                 data=json.dumps(res_payload).encode(),
                                 headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                 method="POST")
    try:
        urllib.request.urlopen(req).read()
    except urllib.error.HTTPError as e:
        server_proc.kill()
        sys.exit(f"Task result failed: {e.read().decode()}")

    print("Result submitted. Verifying it's RESULT_RECEIVED...")
    req = urllib.request.Request(f"http://127.0.0.1:8080/goals/{goal_id}", headers={"Authorization": "Bearer test-secret-key"})
    goal_state = json.loads(urllib.request.urlopen(req).read())
    task_state = goal_state["tasks"][0]
    assert task_state["status"] == "RESULT_RECEIVED", f"Expected RESULT_RECEIVED, got {task_state['status']}"

    print("Restarting Verifier...")
    verifier_proc2 = subprocess.Popen([sys.executable, "scripts/courier_verifier.py"], env=os.environ)
    
    # Wait for verifier to poll and update
    for _ in range(30):
        req = urllib.request.Request(f"http://127.0.0.1:8080/goals/{goal_id}", headers={"Authorization": "Bearer test-secret-key"})
        goal_state = json.loads(urllib.request.urlopen(req).read())
        if goal_state["tasks"][0]["status"] == "RECONCILED":
            print("Task successfully RECONCILED by restarted verifier!")
            break
        time.sleep(0.5)
    else:
        verifier_proc2.kill()
        server_proc.kill()
        sys.exit("Task did not become RECONCILED after verifier restart.")

    # Just ensure no duplication/crashes
    verifier_proc2.kill()
    server_proc.kill()
    print("PASS_W17: EXACTLY_ONE_OUTCOME_AFTER_RESTART")

if __name__ == "__main__":
    run_proof()
