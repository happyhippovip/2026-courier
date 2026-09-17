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

    print("Starting Courier Server (Motor)...")
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

    print("Server is up. Submitting goal with multiple tasks...")
    plan = [
        {"task_id": "T-W18-1", "instruction": "Task 1", "target_agent": "linux"},
        {"task_id": "T-W18-2", "instruction": "Task 2", "target_agent": "linux", "dependencies": ["T-W18-1"]}
    ]
    req = urllib.request.Request("http://127.0.0.1:8080/goals", 
                                 data=json.dumps({"goal_text": "Verify W18", "workflow_plan": plan, "terminal": True}).encode(), 
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
                                 data=json.dumps({"worker_id": "w18-worker", "capabilities": ["linux"]}).encode(),
                                 headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                 method="POST")
    urllib.request.urlopen(req).read()
    
    req = urllib.request.Request("http://127.0.0.1:8080/tasks/claim",
                                 data=json.dumps({"worker_id": "w18-worker"}).encode(),
                                 headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                 method="POST")
    res = urllib.request.urlopen(req)
    task_data = json.loads(res.read())
    task = task_data["task"]
    task_id = task["task_id"]
    
    # Assert state is IN_PROGRESS for task 1
    req = urllib.request.Request(f"http://127.0.0.1:8080/goals/{goal_id}", headers={"Authorization": "Bearer test-secret-key"})
    goal_state = json.loads(urllib.request.urlopen(req).read())
    
    t1_tasks = next((t for t in goal_state["tasks"] if t["task_id"] == "T-W18-1"), None)
    t1_plan = next(t for t in goal_state["goal"]["workflow_plan"] if t["task_id"] == "T-W18-1")
    t2_plan = next(t for t in goal_state["goal"]["workflow_plan"] if t["task_id"] == "T-W18-2")
    
    assert t1_plan["status"] == "DISPATCHED", f"Expected DISPATCHED in plan, got {t1_plan['status']}"
    assert t1_tasks["status"] == "DISPATCHED", f"Expected DISPATCHED in tasks, got {t1_tasks['status']}"
    assert t2_plan["status"] == "QUEUED", f"Expected QUEUED, got {t2_plan['status']}"
    
    print("Restarting Server (Motor) during active work...")
    server_proc.kill()
    server_proc.wait()
    
    server_proc = subprocess.Popen([sys.executable, "-m", "flask", "--app", "server.app:app", "run", "--port", "8080"], env=os.environ)
    for _ in range(30):
        try:
            req = urllib.request.Request("http://127.0.0.1:8080/health")
            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    break
        except Exception:
            time.sleep(0.5)

    print("Checking if state survived motor restart...")
    req = urllib.request.Request(f"http://127.0.0.1:8080/goals/{goal_id}", headers={"Authorization": "Bearer test-secret-key"})
    goal_state = json.loads(urllib.request.urlopen(req).read())
    
    t1_tasks = next((t for t in goal_state["tasks"] if t["task_id"] == "T-W18-1"), None)
    t1_plan = next(t for t in goal_state["goal"]["workflow_plan"] if t["task_id"] == "T-W18-1")
    t2_plan = next(t for t in goal_state["goal"]["workflow_plan"] if t["task_id"] == "T-W18-2")
    
    assert t1_plan["status"] == "DISPATCHED", f"Expected DISPATCHED in plan after restart, got {t1_plan['status']}"
    assert t1_tasks["status"] == "DISPATCHED", f"Expected DISPATCHED in tasks after restart, got {t1_tasks['status']}"
    assert t2_plan["status"] == "QUEUED", f"Expected QUEUED after restart, got {t2_plan['status']}"
    assert t1_tasks["worker_id"] == "w18-worker", "Worker lease lost!"

    print("Submitting task result...")
    res_payload = {
        "task_id": task_id,
        "goal_id": goal_id,
        "run_id": task.get("run_id") or "test-run",
        "worker_id": "w18-worker",
        "result_id": f"res-{uuid4().hex[:8]}",
        "attempt_id": task.get("attempt_id"),
        "dispatch_id": task.get("dispatch_id"),
        "execution_ref": task.get("execution_ref"),
        "status": "SUCCESS",
        "artifacts": [{"path": "dummy.txt", "sha256": "d3eb539a556352f3f47881d71fb0e5777b2f3e9a4251d283c18c67ce996774b7"}],
        "result_data": {"test": "w18"}
    }
    req = urllib.request.Request("http://127.0.0.1:8080/tasks/result",
                                 data=json.dumps(res_payload).encode(),
                                 headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                 method="POST")
    urllib.request.urlopen(req).read()

    server_proc.kill()
    server_proc.wait()
    print("PASS_W18: MOTOR_RESTART_RECOVERY_SUCCESSFUL")

if __name__ == "__main__":
    run_proof()
