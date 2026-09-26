import os, sys, time, subprocess, json, urllib.request

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def run_proof():
    print("Testing W30 FAILURE OF ONE BRANCH DOES NOT CORRUPT OTHERS...")
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
                                    data=json.dumps({"worker_id": "w30-worker-1", "capabilities": ["windows"]}).encode(),
                                    headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                    method="POST")
        urllib.request.urlopen(req)
        
        req = urllib.request.Request("http://127.0.0.1:8080/workers/register",
                                    data=json.dumps({"worker_id": "w30-worker-2", "capabilities": ["windows"]}).encode(),
                                    headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                    method="POST")
        urllib.request.urlopen(req)

        print("Submitting goal with DAG...")
        plan = [
            {"task_id": "T-W30-A", "instruction": "A", "target_agent": "windows"},
            {"task_id": "T-W30-B", "instruction": "B", "target_agent": "windows"},
            {"task_id": "T-W30-C", "instruction": "C", "target_agent": "windows", "depends_on": ["T-W30-A"]},
            {"task_id": "T-W30-D", "instruction": "D", "target_agent": "windows", "depends_on": ["T-W30-B"]}
        ]
        
        req = urllib.request.Request("http://127.0.0.1:8080/goals", 
                                     data=json.dumps({"goal_text": "Verify W30", "workflow_plan": plan, "terminal": True}).encode(), 
                                     headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                     method="POST")
        urllib.request.urlopen(req)
        
        def claim(worker_id):
            req = urllib.request.Request("http://127.0.0.1:8080/tasks/claim",
                                         data=json.dumps({"worker_id": worker_id}).encode(),
                                         headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                         method="POST")
            res = json.loads(urllib.request.urlopen(req).read())
            return res.get("task")
            
        def provider_wait(task, worker_id):
            req = urllib.request.Request(f"http://127.0.0.1:8080/tasks/{task['task_id']}/provider_wait",
                                         data=json.dumps({"worker_id": worker_id, "wait_type": "WAITING_PROVIDER", "reason": "Rate limited"}).encode(),
                                         headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                         method="POST")
            urllib.request.urlopen(req)

        def submit_result(task, worker_id):
            filename = f"courier_canary_{task['task_id']}.txt"
            with open(filename, "wb") as f:
                f.write(b"canary")
            import hashlib
            digest = hashlib.sha256(b"canary").hexdigest()
            result_data = {
                "task_id": task["task_id"],
                "worker_id": worker_id,
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
                "verifier_id": "w30-verifier",
                "result_id": f"res-{task['task_id']}",
                "verdict": "PASS",
                "artifacts": [{"path": filename, "sha256": digest}],
                "received_runtime_identity": task.get("server_binding")
            }
            req = urllib.request.Request("http://127.0.0.1:8080/tasks/verify",
                                        data=json.dumps(verify_data).encode(),
                                        headers={"Authorization": "Bearer test-verifier-key", "Content-Type": "application/json"},
                                        method="POST")
            urllib.request.urlopen(req)

        # Claim 1: Should be A or B
        t1 = claim("w30-worker-1")
        if not t1 or t1["task_id"] not in ["T-W30-A", "T-W30-B"]:
            sys.exit(f"Expected A or B, got {t1}")
            
        # We transiently block t1
        provider_wait(t1, "w30-worker-1")
        
        # Now t1 is WAITING_PROVIDER, but B should still be claimable by the other worker.
        t2 = claim("w30-worker-2")
        if not t2 or t2["task_id"] not in ["T-W30-A", "T-W30-B"] or t2["task_id"] == t1["task_id"]:
            sys.exit(f"Expected the other independent task, got {t2}")
            
        # Submit and verify t2
        submit_result(t2, "w30-worker-2")
        verify_result(t2)
        
        # t2 is RECONCILED. So its dependent should be available.
        # Dependent of A is C. Dependent of B is D.
        t2_dependent = "T-W30-C" if t2["task_id"] == "T-W30-A" else "T-W30-D"
        t1_dependent = "T-W30-C" if t1["task_id"] == "T-W30-A" else "T-W30-D"
        
        t3 = claim("w30-worker-2")
        if not t3 or t3["task_id"] != t2_dependent:
            sys.exit(f"Expected {t2_dependent} because its parent {t2['task_id']} is reconciled, got {t3}")
            
        # We submit t3 to free the worker
        submit_result(t3, "w30-worker-2")
        verify_result(t3)
        
        # Now there should be NO tasks available for worker 2, because t1 is in backoff (WAITING_PROVIDER)
        # and its dependent t1_dependent is blocked.
        t4 = claim("w30-worker-2")
        if t4 is not None:
            sys.exit(f"Expected no tasks (t1 sleeping, dependent blocked), but got {t4}")
            
        print("PASS_W30: FAILURE OF ONE BRANCH DOES NOT CORRUPT OTHERS")
        
    finally:
        server_proc.kill()

if __name__ == "__main__":
    run_proof()
