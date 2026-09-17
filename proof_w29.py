import os, sys, time, subprocess, json, urllib.request

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def run_proof():
    print("Testing W29 DEPENDENCY DAG ORDERING...")
    os.environ["COURIER_STATE_FILE"] = os.path.abspath("test_central_state.json")
    if os.path.exists("test_central_state.json"):
        os.remove("test_central_state.json")
        
    os.environ["COURIER_API_KEY"] = "test-secret-key"
    os.environ["COURIER_VERIFIER_API_KEY"] = "test-verifier-key"
    
    server_proc = subprocess.Popen([sys.executable, "-m", "flask", "--app", "server.app:app", "run", "--port", "8080"], env=os.environ)
    
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
        req = urllib.request.Request("http://127.0.0.1:8080/workers/register",
                                    data=json.dumps({"worker_id": "w29-worker", "capabilities": ["windows"]}).encode(),
                                    headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                    method="POST")
        urllib.request.urlopen(req)

        print("Submitting goal with DAG...")
        plan = [
            {"task_id": "T-W29-A", "instruction": "A", "target_agent": "windows"},
            {"task_id": "T-W29-B", "instruction": "B", "target_agent": "windows"},
            {"task_id": "T-W29-C", "instruction": "C", "target_agent": "windows", "depends_on": ["T-W29-A"]},
            {"task_id": "T-W29-D", "instruction": "D", "target_agent": "windows", "depends_on": ["T-W29-A", "T-W29-B"]}
        ]
        
        req = urllib.request.Request("http://127.0.0.1:8080/goals", 
                                     data=json.dumps({"goal_text": "Verify W29", "workflow_plan": plan, "terminal": True}).encode(), 
                                     headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                     method="POST")
        urllib.request.urlopen(req)
        
        def claim():
            req = urllib.request.Request("http://127.0.0.1:8080/tasks/claim",
                                         data=json.dumps({"worker_id": "w29-worker"}).encode(),
                                         headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                         method="POST")
            res = json.loads(urllib.request.urlopen(req).read())
            return res.get("task")
            
        def submit_result(task):
            filename = f"courier_canary_{task['task_id']}.txt"
            with open(filename, "wb") as f:
                f.write(b"canary")
            import hashlib
            digest = hashlib.sha256(b"canary").hexdigest()
            result_data = {
                "task_id": task["task_id"],
                "worker_id": "w29-worker",
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
                "verifier_id": "w29-verifier",
                "result_id": f"res-{task['task_id']}",
                "verdict": "PASS",
                "artifacts": [{"path": filename, "sha256": digest}],
            }
            req = urllib.request.Request("http://127.0.0.1:8080/tasks/verify",
                                        data=json.dumps(verify_data).encode(),
                                        headers={"Authorization": "Bearer test-verifier-key", "Content-Type": "application/json"},
                                        method="POST")
            urllib.request.urlopen(req)

        # Claim 1: Should be A or B
        t1 = claim()
        if not t1 or t1["task_id"] not in ["T-W29-A", "T-W29-B"]:
            sys.exit(f"Expected A or B, got {t1}")
            
        # Submit result for t1
        submit_result(t1)
        
        # After result received, t1 is RESULT_RECEIVED but not RECONCILED.
        # It shouldn't unblock C or D yet!
        
        # Claim 2: Should be the other of A or B, since C and D are blocked
        t2 = claim()
        if not t2 or set([t1["task_id"], t2["task_id"]]) != {"T-W29-A", "T-W29-B"}:
            sys.exit(f"Expected to get the other parallel task, got {t2}")
            
        submit_result(t2)
        
        # Now both A and B are RESULT_RECEIVED. Claim 3 should return None because C and D still wait for RECONCILED!
        t3_attempt = claim()
        if t3_attempt is not None:
            sys.exit(f"Expected no tasks since dependencies are not RECONCILED, but got {t3_attempt}")
            
        # Verify A and B to make them RECONCILED
        verify_result(t1)
        verify_result(t2)
        
        # Now C and D should be available
        t3 = claim()
        if not t3 or t3["task_id"] not in ["T-W29-C", "T-W29-D"]:
            sys.exit(f"Expected C or D, got {t3}")
            
        submit_result(t3)
        verify_result(t3)
            
        t4 = claim()
        if not t4 or set([t3["task_id"], t4["task_id"]]) != {"T-W29-C", "T-W29-D"}:
            sys.exit(f"Expected C and D, got {t3} and {t4}")
            
        print("PASS_W29: DEPENDENCY DAG ORDERING")
        
    finally:
        server_proc.kill()

if __name__ == "__main__":
    run_proof()
