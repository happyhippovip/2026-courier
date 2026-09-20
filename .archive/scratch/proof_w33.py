import os, sys, time, subprocess, json, urllib.request, threading

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

if len(sys.argv) > 1 and sys.argv[1] == "run_mocked_server":
    from server.app import app
    from scripts.run_chief_commander import ChiefCommander
    
    original_formulate = ChiefCommander.formulate_workflow_plan
    
    replenish_counter = 0
    def mocked_formulate(self, idea_text, idea_type="IDEA", context_delta=None, correlation_id=None):
        global replenish_counter
        if idea_text == "W33_SPECIAL_GOAL":
            replenish_counter += 1
            if replenish_counter <= 5:
                steps = [{"task_id": f"T-W33-{replenish_counter}-{i}", "instruction": f"Batch {replenish_counter} Step {i}", "target_agent": "windows"} for i in range(5)]
                return "Mocked", steps
            else:
                return "Mocked", []
        return original_formulate(self, idea_text, idea_type, context_delta, correlation_id)
        
    ChiefCommander.formulate_workflow_plan = mocked_formulate
    
    # Disable reloader so our mock stays
    app.run(port=8080, use_reloader=False)
    sys.exit(0)

def run_proof():
    print("Testing W33 20-TASK MULTI-BATCH REPLENISH PROOF...")
    os.environ["COURIER_STATE_FILE"] = os.path.abspath("test_central_state_w33.json")
    if os.path.exists("test_central_state_w33.json"):
        os.remove("test_central_state_w33.json")
        
    os.environ["COURIER_API_KEY"] = "test-secret-key"
    os.environ["COURIER_VERIFIER_API_KEY"] = "test-verifier-key"
    
    server_proc = subprocess.Popen([sys.executable, "proof_w33.py", "run_mocked_server"], env=os.environ)
    
    def wait_for_port(port):
        for _ in range(30):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/health")
                break
            except Exception:
                time.sleep(0.5)
        else:
            server_proc.kill()
            sys.exit(f"Port {port} failed to start")
            
    wait_for_port(8080)
    
    try:
        def register_worker(w_id):
            req = urllib.request.Request("http://127.0.0.1:8080/workers/register",
                                        data=json.dumps({"worker_id": w_id, "capabilities": ["windows"]}).encode(),
                                        headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                        method="POST")
            urllib.request.urlopen(req)

        register_worker("w33-worker")

        print("Submitting W33 goal...")
        req = urllib.request.Request("http://127.0.0.1:8080/goals", 
                                     data=json.dumps({"goal_text": "W33_SPECIAL_GOAL", "terminal": False}).encode(), 
                                     headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                     method="POST")
        urllib.request.urlopen(req)
        
        def claim(w_id):
            req = urllib.request.Request("http://127.0.0.1:8080/tasks/claim",
                                         data=json.dumps({"worker_id": w_id}).encode(),
                                         headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                         method="POST")
            res = json.loads(urllib.request.urlopen(req).read())
            return res.get("task")
            
        def submit_result(task, w_id):
            filename = f"courier_canary_{task['task_id']}.txt"
            with open(filename, "wb") as f:
                f.write(b"canary")
            import hashlib
            digest = hashlib.sha256(b"canary").hexdigest()
            result_data = {
                "task_id": task["task_id"],
                "worker_id": w_id,
                "result_id": f"res-{task['task_id']}",
                "attempt_id": task.get("attempt_id"),
                "dispatch_id": task.get("dispatch_id"),
                "execution_ref": task.get("execution_ref"),
                "goal_id": task.get("goal_id"),
                "run_id": "simulated_run",
                "status": "SUCCESS",
                "artifacts": [{"path": filename, "sha256": digest}],
                "stdout": "done",
                "stderr": ""
            }
            req = urllib.request.Request("http://127.0.0.1:8080/tasks/result",
                                        data=json.dumps(result_data).encode(),
                                        headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                        method="POST")
            urllib.request.urlopen(req)
            
        def verify_result(task):
            filename = f"courier_canary_{task['task_id']}.txt"
            import hashlib
            digest = hashlib.sha256(b"canary").hexdigest()
            verify_data = {
                "task_id": task["task_id"],
                "verifier_id": "w33-verifier",
                "result_id": f"res-{task['task_id']}",
                "verdict": "PASS",
                "artifacts": [{"path": filename, "sha256": digest}],
            }
            req = urllib.request.Request("http://127.0.0.1:8080/tasks/verify",
                                        data=json.dumps(verify_data).encode(),
                                        headers={"Authorization": "Bearer test-verifier-key", "Content-Type": "application/json"},
                                        method="POST")
            urllib.request.urlopen(req)

        completed_tasks = []
        consecutive_empty = 0
        
        while True:
            task = claim("w33-worker")
            if task:
                submit_result(task, "w33-worker")
                verify_result(task)
                completed_tasks.append(task["task_id"])
                consecutive_empty = 0
                print(f"Completed task {len(completed_tasks)}: {task['task_id']}")
            else:
                consecutive_empty += 1
                time.sleep(0.1)
                if consecutive_empty > 50:
                    if len(completed_tasks) >= 20:
                        break
                    else:
                        sys.exit(f"Queue stalled with only {len(completed_tasks)} tasks completed")

        print(f"PASS_W33: Completed {len(completed_tasks)} tasks via multiple replenish batches")
        
    finally:
        server_proc.kill()

if __name__ == "__main__":
    run_proof()
