import os, sys, time, subprocess, json, urllib.request

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def run_proof():
    print("Testing W27 WINDOWS + SECOND WORKER WORK STEALING...")
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
            {"task_id": "T-W27-A", "instruction": "echo 'A'", "target_agent": "windows"},
            {"task_id": "T-W27-B", "instruction": "echo 'B'", "target_agent": "windows"}
        ]
        req = urllib.request.Request("http://127.0.0.1:8080/goals", 
                                     data=json.dumps({"goal_text": "Verify W27", "workflow_plan": plan, "terminal": True}).encode(), 
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
            
        if task1["task_id"] == task2["task_id"]:
            sys.exit("Workers stole the SAME task!")
            
        if set([task1["task_id"], task2["task_id"]]) != {"T-W27-A", "T-W27-B"}:
            sys.exit("Workers got unexpected tasks.")
            
        print("PASS_W27: WORK_STEALING")
        
    finally:
        server_proc.kill()

if __name__ == "__main__":
    run_proof()
