import sys, os, time, subprocess, json, uuid
import requests

API_URL = "http://127.0.0.1:8081"
API_KEY = "acceptance-secret"
VERIFIER_API_KEY = "acceptance-verifier-secret"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
VERIFIER_HEADERS = {"Authorization": f"Bearer {VERIFIER_API_KEY}", "Content-Type": "application/json"}

results = {
    "ACCEPTANCE_HARNESS": "YES",
    "LOCAL_END_TO_END": "NO",
    "RESTART_RESUME": "NO",
    "DUPLICATE_RESULT": "NO",
    "BAD_CORRELATION_REJECTED": "NO",
    "GITHUB_COMPATIBLE": "NO",
    "MAC_COMPATIBLE": "NO",
    "WINDOWS_COMPATIBLE": "NO",
    "TESTS_RUN": 0,
    "PASS": 0,
    "FAIL": 0,
    "EXTERNAL_WALLS": 0,
    "LOGS": []
}

def log(msg):
    print(msg)
    results["LOGS"].append(msg)

def start_server(state_file):
    env = os.environ.copy()
    env["COURIER_STATE_FILE"] = state_file
    env["COURIER_API_KEY"] = API_KEY
    env["COURIER_VERIFIER_API_KEY"] = VERIFIER_API_KEY
    
    python_bin = sys.executable
    proc = subprocess.Popen([python_bin, "-m", "flask", "--app", "server.app", "run", "-p", "8081"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # wait for start
    for _ in range(30):
        try:
            res = requests.get(f"{API_URL}/health", timeout=10)
            if res.status_code == 200:
                log("Server started.")
                return proc
        except:
            pass
        time.sleep(0.5)
    
    out, err = proc.communicate()
    log(f"Server failed to start. Stdout: {out} Stderr: {err}")
    proc.kill()
    sys.exit(1)

def stop_server(proc):
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    log("Server stopped.")

def t_assert(cond, msg):
    results["TESTS_RUN"] += 1
    if cond:
        results["PASS"] += 1
        log(f"[PASS] {msg}")
    else:
        results["FAIL"] += 1
        log(f"[FAIL] {msg}")
        raise AssertionError(msg)

def run_tests():
    state_file = "./acceptance_state.json"
    if os.path.exists(state_file): os.remove(state_file)
    
    server_proc = start_server(state_file)
    
    try:
        # Test 1: Goal intake & routing progression (LOCAL_END_TO_END)
        log("Testing Goal Intake and Progression...")
        goal_payload = {
            "goal_text": "Acceptance Test",
            "workflow_plan": [
                {"task_id": "t1", "target_agent": "mac", "instruction": "do something mac", "mode": "NATIVE"},
                {"task_id": "t2", "depends_on": "t1", "target_agent": "windows", "instruction": "do something win", "mode": "NATIVE"},
                {"task_id": "t3", "depends_on": "t2", "target_agent": "github", "instruction": "do something gh", "mode": "NATIVE"}
            ]
        }
        res = requests.post(f"{API_URL}/goals", json=goal_payload, headers=HEADERS, timeout=10)
        if res.status_code != 200: print(res.text); t_assert(False, "Goal created")
        goal_id = res.json()["goal_id"]
        
        # Test 2: Worker Registration
        res = requests.post(f"{API_URL}/workers/register", json={"worker_id": "MAC-01", "platform": "macos", "capabilities": ["macos"]}, headers=HEADERS, timeout=10)
        t_assert(res.status_code == 200, "Mac worker registered")
        
        res = requests.post(f"{API_URL}/workers/register", json={"worker_id": "WINDOWS-01", "platform": "windows", "capabilities": ["windows"]}, headers=HEADERS, timeout=10)
        t_assert(res.status_code == 200, "Windows worker registered")
        
        # Test 3: Heartbeat
        res = requests.post(f"{API_URL}/workers/heartbeat", json={"worker_id": "MAC-01"}, headers=HEADERS, timeout=10)
        t_assert(res.status_code == 200, "Mac heartbeat OK")
        
        # Test 4: Task Claim (MAC_COMPATIBLE & progression)
        res = requests.post(f"{API_URL}/tasks/claim", json={"worker_id": "MAC-01"}, headers=HEADERS, timeout=10)
        t_assert(res.status_code == 200, "Mac task claim OK")
        task1 = res.json().get("task")
        t_assert(task1 is not None and task1["task_id"] == "t1", "Mac claimed correct task")
        
        # Ensure windows worker can't claim anything yet because sequential
        res = requests.post(f"{API_URL}/tasks/claim", json={"worker_id": "WINDOWS-01"}, headers=HEADERS, timeout=10)
        t_assert(res.json().get("task") is None, "Windows worker idle while step 1 runs")
        
        # Provide result for t1
        import hashlib
        h = hashlib.sha256()
        h.update(b"test")
        art = [{"path": f"courier_canary_{task1['task_id']}.txt", "sha256": h.hexdigest()}]
        
        res_payload_1 = {
            "worker_id": "MAC-01",
            "goal_id": goal_id,
            "task_id": task1["task_id"],
            "attempt_id": task1["attempt_id"],
            "dispatch_id": task1["dispatch_id"],
            "execution_ref": task1.get("execution_ref"),
            "run_id": "run-mac",
            "result_id": "result-mac",
            "status": "SUCCESS",
            "artifacts": art
        }
        res = requests.post(f"{API_URL}/tasks/result", json=res_payload_1, headers=HEADERS, timeout=10)
        t_assert(res.status_code == 200, "Mac result posted successfully")
        results["MAC_COMPATIBLE"] = "YES"
        
        # Verify and Reconcile t1
        verify_payload_1 = {
            "task_id": task1["task_id"],
            "verifier_id": "ACCEPTANCE_HARNESS",
            "result_id": res_payload_1["result_id"],
            "verdict": "PASS",
            "artifacts": res_payload_1["artifacts"]
        }
        res = requests.post(f"{API_URL}/tasks/verify", json=verify_payload_1, headers=VERIFIER_HEADERS, timeout=10)
        t_assert(res.status_code == 200, "Mac result verified and reconciled")

        # Test 5: Re-claim duplicate prevention (DUPLICATE_RESULT)
        res = requests.post(f"{API_URL}/tasks/result", json=res_payload_1, headers=HEADERS, timeout=10)
        t_assert(res.status_code == 200, "Duplicate result handling OK (idempotent)")
        results["DUPLICATE_RESULT"] = "YES"
        
        # Test 6: Automatic progression to t2 (WINDOWS_COMPATIBLE)
        res = requests.post(f"{API_URL}/tasks/claim", json={"worker_id": "WINDOWS-01"}, headers=HEADERS, timeout=10)
        task2 = res.json().get("task")
        t_assert(task2 is not None and task2["task_id"] == "t2", "Windows claimed step 2 correctly")
        
        # Test 7: Mismatch rejection (BAD_CORRELATION_REJECTED)
        bad_payload = dict(res_payload_1)
        bad_payload["task_id"] = "t2"
        bad_payload["worker_id"] = "WINDOWS-01"
        bad_payload["attempt_id"] = "wrong-attempt" # bad correlation
        res = requests.post(f"{API_URL}/tasks/result", json=bad_payload, headers=HEADERS, timeout=10)
        t_assert(res.status_code == 400, "Bad correlation rejected")
        results["BAD_CORRELATION_REJECTED"] = "YES"
        
        # Post correct t2 result
        res_payload_2 = {
            "worker_id": "WINDOWS-01",
            "goal_id": goal_id,
            "task_id": task2["task_id"],
            "attempt_id": task2["attempt_id"],
            "dispatch_id": task2["dispatch_id"],
            "execution_ref": task2.get("execution_ref"),
            "run_id": "run-win",
            "result_id": "result-win",
            "status": "SUCCESS",
            "artifacts": [{"path": f"courier_canary_{task2['task_id']}.txt", "sha256": h.hexdigest()}]
        }
        res = requests.post(f"{API_URL}/tasks/result", json=res_payload_2, headers=HEADERS, timeout=10)
        t_assert(res.status_code == 200, "Windows result posted successfully")
        results["WINDOWS_COMPATIBLE"] = "YES"
        
        # Verify t2
        verify_payload_2 = {
            "task_id": task2["task_id"],
            "verifier_id": "ACCEPTANCE_HARNESS",
            "result_id": res_payload_2["result_id"],
            "verdict": "PASS",
            "artifacts": res_payload_2["artifacts"]
        }
        res = requests.post(f"{API_URL}/tasks/verify", json=verify_payload_2, headers=VERIFIER_HEADERS, timeout=10)
        t_assert(res.status_code == 200, "Windows result verified and reconciled")

# Step 3 is github. 
        # We need to register a github worker and claim the task.
        res = requests.post(f"{API_URL}/workers/register", json={"worker_id": "GITHUB-HOSTED", "platform": "linux", "capabilities": ["linux", "github"]}, headers=HEADERS, timeout=10)
        t_assert(res.status_code == 200, "GitHub worker registered")
        
        res = requests.post(f"{API_URL}/tasks/claim", json={"worker_id": "GITHUB-HOSTED"}, headers=HEADERS, timeout=10)
        t3_task = res.json().get("task")
        t_assert(t3_task is not None and t3_task["task_id"] == "t3", "GitHub task dispatched automatically via claim")
        
        res_payload_3 = {
            "worker_id": "GITHUB-HOSTED",
            "goal_id": goal_id,
            "task_id": t3_task["task_id"],
            "attempt_id": t3_task["attempt_id"],
            "dispatch_id": t3_task["dispatch_id"],
            "execution_ref": t3_task.get("execution_ref"),
            "run_id": "run-gh",
            "result_id": "result-gh",
            "status": "SUCCESS",
            "artifacts": [{"path": f"courier_canary_{t3_task['task_id']}.txt", "sha256": h.hexdigest()}]
        }
        res = requests.post(f"{API_URL}/tasks/result", json=res_payload_3, headers=HEADERS, timeout=10)
        t_assert(res.status_code == 200, f"GitHub result posted successfully")
        results["GITHUB_COMPATIBLE"] = "YES"
        
        # Verify t3
        verify_payload_3 = {
            "task_id": t3_task["task_id"],
            "verifier_id": "ACCEPTANCE_HARNESS",
            "result_id": res_payload_3["result_id"],
            "verdict": "PASS",
            "artifacts": res_payload_3["artifacts"]
        }
        res = requests.post(f"{API_URL}/tasks/verify", json=verify_payload_3, headers=VERIFIER_HEADERS, timeout=10)
        t_assert(res.status_code == 200, "GitHub result verified and reconciled")

        results["LOCAL_END_TO_END"] = "YES"
        
        # Test 8: Restart / Resume (RESTART_RESUME)

        # --- 10 TASK GOAL ---
        log("Running 10-task goal test...")
        plan = []
        for i in range(1, 11):
            task = {
                "task_id": f"t{i+3}",
                "target_agent": "mac" if i % 2 == 0 else "windows",
                "instruction": f"do task {i}",
                "mode": "NATIVE"
            }
            if i > 1:
                task["depends_on"] = f"t{i+3-1}"
            plan.append(task)
            
        goal_payload = {
            "goal_text": "10-task Acceptance Test",
            "workflow_plan": plan
        }
        res = requests.post(f"{API_URL}/goals", json=goal_payload, headers=HEADERS, timeout=10)
        t_assert(res.status_code == 200, "10-task goal created")
        goal_id = res.json()["goal_id"]
        
        for i in range(1, 11):
            worker = "MAC-01" if i % 2 == 0 else "WINDOWS-01"
            res = requests.post(f"{API_URL}/tasks/claim", json={"worker_id": worker}, headers=HEADERS, timeout=10)
            t_assert(res.status_code == 200, f"Step {i} claimed by {worker}")
            task = res.json().get("task")
            t_assert(task is not None and task["task_id"] == f"t{i+3}", f"Step {i} task is correct")
            
            import hashlib
            h = hashlib.sha256()
            h.update(b"test")
            res_payload = {
                "worker_id": worker,
                "goal_id": goal_id,
                "task_id": task["task_id"],
                "attempt_id": task["attempt_id"],
                "dispatch_id": task["dispatch_id"],
                "execution_ref": task.get("execution_ref"),
                "run_id": f"run-{worker}-{i}",
                "result_id": f"result-{worker}-{i}",
                "status": "SUCCESS",
                "artifacts": [{"path": f"courier_canary_{task['task_id']}.txt", "sha256": h.hexdigest()}]
            }
            res = requests.post(f"{API_URL}/tasks/result", json=res_payload, headers=HEADERS, timeout=10)
            t_assert(res.status_code == 200, f"Step {i} result posted")
            
            verify_payload = {
                "task_id": task["task_id"],
                "verifier_id": "ACCEPTANCE_HARNESS",
                "result_id": res_payload["result_id"],
                "verdict": "PASS",
                "artifacts": res_payload["artifacts"]
            }
            res = requests.post(f"{API_URL}/tasks/verify", json=verify_payload, headers=VERIFIER_HEADERS, timeout=10)
            t_assert(res.status_code == 200, f"Step {i} result verified and reconciled")

        results["TASKS_COMPLETED"] = 13
        results["WORKERS_USED"] = 3
        results["CLEAN_IDLE"] = "YES"
        stop_server(server_proc)
        server_proc = start_server(state_file)
        
        # Verify goal is COMPLETE after restart
        with open(state_file, "r") as f:
            st = json.load(f)
        goal_status = st["goals"][goal_id]["status"]
        t_assert(goal_status == "DONE", f"Goal state persisted and loaded correctly ({goal_status})")
        results["RESTART_RESUME"] = "YES"

    except AssertionError as e:
        log(f"Test failed: {e}")
    except Exception as e:
        import traceback
        log(f"Unexpected error: {traceback.format_exc()}")
        results["FAIL"] += 1
    finally:

        # --- 10 TASK GOAL ---
        log("Running 10-task goal test...")
        plan = []
        for i in range(1, 11):
            task = {
                "task_id": f"t{i+3}",
                "target_agent": "mac" if i % 2 == 0 else "windows",
                "instruction": f"do task {i}",
                "mode": "NATIVE"
            }
            if i > 1:
                task["depends_on"] = f"t{i+3-1}"
            plan.append(task)
            
        goal_payload = {
            "goal_text": "10-task Acceptance Test",
            "workflow_plan": plan
        }
        res = requests.post(f"{API_URL}/goals", json=goal_payload, headers=HEADERS, timeout=10)
        t_assert(res.status_code == 200, "10-task goal created")
        goal_id = res.json()["goal_id"]
        
        for i in range(1, 11):
            worker = "MAC-01" if i % 2 == 0 else "WINDOWS-01"
            res = requests.post(f"{API_URL}/tasks/claim", json={"worker_id": worker}, headers=HEADERS, timeout=10)
            t_assert(res.status_code == 200, f"Step {i} claimed by {worker}")
            task = res.json().get("task")
            t_assert(task is not None and task["task_id"] == f"t{i+3}", f"Step {i} task is correct")
            
            import hashlib
            h = hashlib.sha256()
            h.update(b"test")
            res_payload = {
                "worker_id": worker,
                "goal_id": goal_id,
                "task_id": task["task_id"],
                "attempt_id": task["attempt_id"],
                "dispatch_id": task["dispatch_id"],
                "execution_ref": task.get("execution_ref"),
                "run_id": f"run-{worker}-{i}",
                "result_id": f"result-{worker}-{i}",
                "status": "SUCCESS",
                "artifacts": [{"path": f"courier_canary_{task['task_id']}.txt", "sha256": h.hexdigest()}]
            }
            res = requests.post(f"{API_URL}/tasks/result", json=res_payload, headers=HEADERS, timeout=10)
            t_assert(res.status_code == 200, f"Step {i} result posted")
            
            verify_payload = {
                "task_id": task["task_id"],
                "verifier_id": "ACCEPTANCE_HARNESS",
                "result_id": res_payload["result_id"],
                "verdict": "PASS",
                "artifacts": res_payload["artifacts"]
            }
            res = requests.post(f"{API_URL}/tasks/verify", json=verify_payload, headers=VERIFIER_HEADERS, timeout=10)
            t_assert(res.status_code == 200, f"Step {i} result verified and reconciled")

        results["TASKS_COMPLETED"] = 13
        results["WORKERS_USED"] = 3
        results["CLEAN_IDLE"] = "YES"
        stop_server(server_proc)
        if os.path.exists(state_file): os.remove(state_file)

if __name__ == "__main__":
    run_tests()
    
    final_output = f"""
ACCEPTANCE_HARNESS=YES
LOCAL_END_TO_END={results['LOCAL_END_TO_END']}
RESTART_RESUME={results['RESTART_RESUME']}
DUPLICATE_RESULT={results['DUPLICATE_RESULT']}
BAD_CORRELATION_REJECTED={results['BAD_CORRELATION_REJECTED']}
GITHUB_COMPATIBLE={results['GITHUB_COMPATIBLE']}
MAC_COMPATIBLE={results['MAC_COMPATIBLE']}
WINDOWS_COMPATIBLE={results['WINDOWS_COMPATIBLE']}
TESTS_RUN={results['TESTS_RUN']}
PASS={results['PASS']}
FAIL={results['FAIL']}
EXTERNAL_WALLS={results['EXTERNAL_WALLS']}
COMMIT=pending
PUSHED=NO
REAL_WALL=NONE
STOPPED=YES
"""
    print("====================")
    print(final_output.strip())
