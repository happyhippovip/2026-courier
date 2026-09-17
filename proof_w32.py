import os, sys, time, subprocess, json, urllib.request

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def run_proof():
    print("Testing W31 10-TASK ZERO-TOUCH ACCEPTANCE...")
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
        def register_worker(w_id):
            req = urllib.request.Request("http://127.0.0.1:8080/workers/register",
                                        data=json.dumps({"worker_id": w_id, "capabilities": ["windows"]}).encode(),
                                        headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                        method="POST")
            urllib.request.urlopen(req)

        register_worker("w32-worker1")
        register_worker("w32-worker2")

        def run_goal(goal_id_prefix, task_count):
            print(f"Submitting goal {goal_id_prefix} with {task_count} tasks...")
            plan = [{"task_id": f"{goal_id_prefix}-{i}", "instruction": f"Do step {i}", "target_agent": "windows"} for i in range(task_count)]
            
            req = urllib.request.Request("http://127.0.0.1:8080/goals", 
                                         data=json.dumps({"goal_text": f"Verify {goal_id_prefix}", "workflow_plan": plan, "terminal": True}).encode(), 
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
                    "verifier_id": "w32-verifier",
                    "result_id": f"res-{task['task_id']}",
                    "verdict": "PASS",
                    "artifacts": [{"path": filename, "sha256": digest}],
                }
                req = urllib.request.Request("http://127.0.0.1:8080/tasks/verify",
                                            data=json.dumps(verify_data).encode(),
                                            headers={"Authorization": "Bearer test-verifier-key", "Content-Type": "application/json"},
                                            method="POST")
                urllib.request.urlopen(req)

            import threading
            completed_tasks = []
            lock = threading.Lock()
            
            def worker_loop(w_id):
                while True:
                    task = claim(w_id)
                    if not task:
                        break # No more tasks available for this goal yet, or goal is done
                    submit_result(task, w_id)
                    verify_result(task)
                    with lock:
                        completed_tasks.append(task["task_id"])
                        
            # Wait, claim returns None if worker is busy or NO tasks are available.
            # So worker_loop will exit immediately if it grabs no task initially.
            # We need to loop until tasks == task_count
            
            def worker_run(w_id):
                while True:
                    with lock:
                        if len(completed_tasks) >= task_count:
                            break
                    task = claim(w_id)
                    if task:
                        submit_result(task, w_id)
                        verify_result(task)
                        with lock:
                            completed_tasks.append(task["task_id"])
                    else:
                        time.sleep(0.1)

            t1 = threading.Thread(target=worker_run, args=("w32-worker1",))
            t2 = threading.Thread(target=worker_run, args=("w32-worker2",))
            
            t1.start()
            t2.start()
            t1.join()
            t2.join()
            
            if len(completed_tasks) != task_count:
                sys.exit(f"Expected {task_count} tasks completed, got {len(completed_tasks)}")
                
        # Goal 1
        run_goal("T-W32-G1", 5)
        # Goal 2 without restarting server
        run_goal("T-W32-G2", 5)
            
        print("PASS_W32: SECOND DISTINCT GOAL WITHOUT RUNTIME RESTART")
        
    finally:
        server_proc.kill()

if __name__ == "__main__":
    run_proof()
