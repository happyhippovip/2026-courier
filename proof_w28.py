import os, sys, time, subprocess, json, urllib.request

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def run_proof():
    print("Testing W28 TWO-WORKER CONCURRENT RECONCILIATION...")
    os.environ["COURIER_STATE_FILE"] = os.path.abspath("test_central_state.json")
    if os.path.exists("test_central_state.json"):
        os.remove("test_central_state.json")
        
    os.environ["COURIER_API_KEY"] = "test-secret-key"
    
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
        from scripts.windows_worker import daemon
        import importlib
        importlib.reload(daemon)
        
        print("Registering workers...")
        daemon.register_worker("w27-worker-1")
        daemon.register_worker("w27-worker-2")
        
        print("Submitting goal with 2 parallel tasks...")
        plan = [
            {"task_id": "T-W28-A", "instruction": "echo 'A' > courier_canary_T-W28-A.txt", "target_agent": "windows"},
            {"task_id": "T-W28-B", "instruction": "echo 'B' > courier_canary_T-W28-B.txt", "target_agent": "windows"}
        ]
        req = urllib.request.Request("http://127.0.0.1:8080/goals", 
                                     data=json.dumps({"goal_text": "Verify W28", "workflow_plan": plan, "terminal": True}).encode(), 
                                     headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                     method="POST")
        urllib.request.urlopen(req)
        
        # Worker 1 claim
        req1 = urllib.request.Request("http://127.0.0.1:8080/tasks/claim",
                                     data=json.dumps({"worker_id": "w27-worker-1"}).encode(),
                                     headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                     method="POST")
        res1 = json.loads(urllib.request.urlopen(req1).read())
        task1 = res1.get("task", {})
        
        # Worker 2 claim
        req2 = urllib.request.Request("http://127.0.0.1:8080/tasks/claim",
                                     data=json.dumps({"worker_id": "w27-worker-2"}).encode(),
                                     headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                     method="POST")
        res2 = json.loads(urllib.request.urlopen(req2).read())
        task2 = res2.get("task", {})
        
        print(f"Worker 1 got: {task1.get('task_id')}")
        print(f"Worker 2 got: {task2.get('task_id')}")
        
        if not task1 or not task2:
            sys.exit("Workers did not get tasks.")
            
        # Concurrently send results
        import threading
        
        def send_result(task, worker_id):
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
            try:
                urllib.request.urlopen(req)
            except urllib.error.HTTPError as e:
                print(f"Error {e.code}: {e.read().decode()}")

        t1 = threading.Thread(target=send_result, args=(task1, "w27-worker-1"))
        t2 = threading.Thread(target=send_result, args=(task2, "w27-worker-2"))
        
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        
        # Now verify state
        req_state = urllib.request.Request("http://127.0.0.1:8080/status",
                                     headers={"Authorization": "Bearer test-secret-key"},
                                     method="GET")
        res_state = json.loads(urllib.request.urlopen(req_state).read())
        print(res_state)
        
        with open("test_central_state.json", "r") as f:
            state = json.load(f)
        
        t1_status = state["tasks"][task1["task_id"]]["status"]
        t2_status = state["tasks"][task2["task_id"]]["status"]
        print(f"Task 1 status: {t1_status}")
        print(f"Task 2 status: {t2_status}")
        
        if t1_status != "RESULT_RECEIVED" or t2_status != "RESULT_RECEIVED":
            sys.exit("Tasks not both RESULT_RECEIVED")
            
        print("PASS_W28: TWO-WORKER CONCURRENT RECONCILIATION")
        
    finally:
        server_proc.kill()

if __name__ == "__main__":
    run_proof()
