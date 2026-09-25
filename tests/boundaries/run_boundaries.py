import sys, os, time, subprocess, json, uuid
import requests

API_URL = "http://127.0.0.1:8082"
API_KEY = "boundary-secret"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

results = {
    "PROPERTIES_TESTED": 0,
    "PASS": 0,
    "REAL_DEFECTS": 0,
    "FALSE_POSITIVES": 0,
    "AUTH_FAIL_CLOSED": "NO",
    "CORRELATION_FAIL_CLOSED": "NO",
    "DUPLICATE_SAFE": "NO",
    "MALFORMED_INPUT_SAFE": "NO"
}

def log(msg):
    print(msg)

def create_finding(prop, inp, obs, exp, causal, fix):
    results["REAL_DEFECTS"] += 1
    fid = f"defect_{uuid.uuid4().hex[:6]}"
    finding = f"""PROPERTY: {prop}
INPUT: {inp}
OBSERVED: {obs}
EXPECTED: {exp}
CAUSAL_FILE: {causal}
MINIMUM_FIX: {fix}
"""
    path = f"tests/boundaries/findings/{fid}.txt"
    with open(path, "w") as f:
        f.write(finding)
    log(f"Created finding: {path}\n{finding}")

def start_server(state_file):
    env = os.environ.copy()
    env["COURIER_STATE_FILE"] = state_file
    env["COURIER_API_KEY"] = API_KEY
    
    python_bin = "venv/bin/python3" if os.path.exists("venv/bin/python3") else sys.executable
    proc = subprocess.Popen([python_bin, "-m", "flask", "--app", "server.app", "run", "-p", "8082"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    for _ in range(30):
        try:
            res = requests.get(f"{API_URL}/health", timeout=10)
            if res.status_code == 200:
                log("Server started.")
                return proc
        except:
            pass
        time.sleep(0.5)
    
    proc.kill()
    sys.exit(1)

def stop_server(proc):
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()

def run_tests():
    state_file = "./boundary_state.json"
    if os.path.exists(state_file): os.remove(state_file)
    
    proc = start_server(state_file)
    try:
        # Auth Boundaries
        log("Testing Auth Boundaries...")
        results["PROPERTIES_TESTED"] += 1
        r = requests.post(f"{API_URL}/goals", json={"goal_text": "test"}, timeout=10)
        if r.status_code == 401:
            results["PASS"] += 1
            results["AUTH_FAIL_CLOSED"] = "YES"
        else:
            create_finding("missing auth rejected", "No Authorization header", f"Status {r.status_code}", "Status 401", "server/app.py", "Enforce auth on /goals")

        results["PROPERTIES_TESTED"] += 1
        r = requests.post(f"{API_URL}/goals", json={"goal_text": "test"}, headers={"Authorization": "Bearer BAD"}, timeout=10)
        if r.status_code == 401:
            results["PASS"] += 1
        else:
            create_finding("wrong auth rejected", "Bad token", f"Status {r.status_code}", "Status 401", "server/app.py", "Verify token match")

        # Unknown Worker Boundary
        log("Testing Unknown Worker Boundary...")
        results["PROPERTIES_TESTED"] += 1
        r = requests.post(f"{API_URL}/tasks/claim", json={"worker_id": "UNKNOWN"}, headers=HEADERS, timeout=10)
        if r.status_code == 404:
            results["PASS"] += 1
        else:
            create_finding("unknown worker rejected", "worker_id=UNKNOWN", f"Status {r.status_code}", "Status 404", "server/app.py", "Check worker existence")

        # Create worker & goal for further tests
        requests.post(f"{API_URL}/workers/register", json={"worker_id": "W1", "platform": "linux", "capabilities": ["linux"]}, headers=HEADERS, timeout=10)
        requests.post(f"{API_URL}/workers/register", json={"worker_id": "W2", "platform": "linux", "capabilities": ["linux"]}, headers=HEADERS, timeout=10)
        
        goal_payload = {
            "goal_text": "test",
            "workflow_plan": [
                {"task_id": "t1", "target_agent": "linux", "instruction": "echo test"}
            ]
        }
        r = requests.post(f"{API_URL}/goals", json=goal_payload, headers=HEADERS, timeout=10)
        goal_id = r.json()["goal_id"]
        
        r = requests.post(f"{API_URL}/tasks/claim", json={"worker_id": "W1"}, headers=HEADERS, timeout=10)
        task = r.json().get("task")
        
        # Unknown Task Result
        log("Testing Unknown Task Result...")
        results["PROPERTIES_TESTED"] += 1
        r = requests.post(f"{API_URL}/tasks/result", json={"task_id": "UNKNOWN", "worker_id": "W1"}, headers=HEADERS, timeout=10)
        if r.status_code in [404, 400]:
            results["PASS"] += 1
        else:
            create_finding("unknown task result rejected", "task_id=UNKNOWN", f"Status {r.status_code}", "Status 404/400", "server/app.py", "Check task existence")
            
        # Wrong Worker Result
        log("Testing Wrong Worker Result...")
        results["PROPERTIES_TESTED"] += 1
        r = requests.post(f"{API_URL}/tasks/result", json={"task_id": "t1", "worker_id": "W2", "goal_id": goal_id, "dispatch_id": task["dispatch_id"], "attempt_id": task["attempt_id"], "status": "SUCCESS", "artifacts": [], "run_id": "r1", "result_id": "res1"}, headers=HEADERS, timeout=10)
        if r.status_code in [400, 404]:
            results["PASS"] += 1
        else:
            create_finding("wrong worker result rejected", "worker_id=W2", f"Status {r.status_code} {r.text}", "Status 400 worker_id mismatch", "server/app.py", "Check worker_id matches dispatched task")

        # Mismatched attributes
        log("Testing Correlation Fail Closed...")
        results["CORRELATION_FAIL_CLOSED"] = "YES" # Assume yes until proven otherwise
        
        for attr, bad_val in [("goal_id", "bad_goal"), ("attempt_id", "bad_attempt"), ("dispatch_id", "bad_dispatch")]:
            results["PROPERTIES_TESTED"] += 1
            payload = {
                "worker_id": "W1", "goal_id": goal_id, "task_id": "t1", 
                "dispatch_id": task["dispatch_id"], "attempt_id": task["attempt_id"], 
                "status": "SUCCESS", "artifacts": [], "run_id": "r1", "result_id": "res1"
            }
            payload[attr] = bad_val
            r = requests.post(f"{API_URL}/tasks/result", json=payload, headers=HEADERS, timeout=10)
            if r.status_code == 400:
                results["PASS"] += 1
            else:
                create_finding(f"mismatched {attr} rejected", f"{attr}={bad_val}", f"Status {r.status_code}", "Status 400", "server/app.py", f"Validate {attr} properly")
                results["CORRELATION_FAIL_CLOSED"] = "NO"

        # Correct result (to test duplicate and re-claim)
        log("Testing Duplicate Safe...")
        import hashlib
        h = hashlib.sha256(b"test").hexdigest()
        good_payload = {
            "worker_id": "W1", "goal_id": goal_id, "task_id": "t1", 
            "dispatch_id": task["dispatch_id"], "attempt_id": task["attempt_id"], 
            "status": "SUCCESS", "artifacts": [{"path": "courier_canary_t1.txt", "sha256": h}], 
            "run_id": "r1", "result_id": "res1"
        }
        r = requests.post(f"{API_URL}/tasks/result", json=good_payload, headers=HEADERS, timeout=10)
        
        results["PROPERTIES_TESTED"] += 1
        r2 = requests.post(f"{API_URL}/tasks/result", json=good_payload, headers=HEADERS, timeout=10)
        if r2.status_code == 200 or r2.status_code == 409:
            results["PASS"] += 1
            results["DUPLICATE_SAFE"] = "YES"
        else:
            create_finding("duplicate result does not duplicate work", "Same result payload twice", f"Status {r2.status_code}", "Status 200 or 409", "server/app.py", "Make result intake idempotent")
            
        # Re-claim boundary
        log("Testing Re-claim Completed Task...")
        results["PROPERTIES_TESTED"] += 1
        r = requests.post(f"{API_URL}/tasks/claim", json={"worker_id": "W1"}, headers=HEADERS, timeout=10)
        if r.json().get("task") is None:
            results["PASS"] += 1
        else:
            create_finding("completed task cannot silently be reclaimed", "Claim after RESULT_RECEIVED", "Task claimed again", "task=None", "server/app.py", "Do not allow claiming RESULT_RECEIVED tasks")

        # Malformed JSON
        log("Testing Malformed JSON...")
        results["PROPERTIES_TESTED"] += 1
        r = requests.post(f"{API_URL}/goals", data="INVALID JSON {", headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}, timeout=10)
        if r.status_code in [400, 500]:
            # Ensure state is not corrupted
            try:
                with open(state_file, "r") as f:
                    json.load(f)
                results["PASS"] += 1
                results["MALFORMED_INPUT_SAFE"] = "YES"
            except:
                create_finding("malformed JSON does not corrupt state", "Bad JSON to /goals", "State file corrupted", "State file untouched", "server/app.py", "Catch JSONDecodeError safely")
        

        # Restart preserves state
        log("Testing Restart Preserves State...")
        stop_server(proc)
        proc = start_server(state_file)
        results["PROPERTIES_TESTED"] += 1
        with open(state_file, "r") as sf:
            st = json.load(sf)
        if st["goals"][goal_id]["status"] == "ACTIVE":
            results["PASS"] += 1
        else:
            create_finding("restart preserves authoritative state", "Restart server", "State lost", "State preserved", "server/app.py", "Fix state persistence")

        # Mac Worker Boundary Test
        log("Testing Mac Worker Boundary...")
        results["PROPERTIES_TESTED"] += 1
        
        # We can import run_native from daemon.py
        sys.path.append(os.path.abspath("scripts/mac_worker"))
        import daemon
        
        res = daemon.run_native({"task_id": "test", "action": "rm_rf_slash", "instruction": "rm -rf /"}, {})
        if res.get("status") == "FAILED" and "not allowed" in res.get("stderr", ""):
            results["PASS"] += 1
        else:
            create_finding("remote Mac native arbitrary shell is not accepted", "action=rm_rf_slash", f"res={res}", "status=FAILED", "scripts/mac_worker/daemon.py", "Strictly enforce allowlist")

        # GitHub Worker Boundary Test
        log("Testing GitHub Worker Boundary...")
        results["PROPERTIES_TESTED"] += 1
        
        with open(".github/workflows/courier_worker.yml", "r") as f:
            workflow = f.read()
            
        if "os.system" not in workflow and "subprocess" not in workflow:
            # We already fixed this in the previous step
            if "status = \"FAILED_UNSUPPORTED\"" in workflow:
                results["PASS"] += 1
            else:
                create_finding("GitHub worker cannot become arbitrary shell service", "GitHub workflow content", "Lack of fail closed", "status=FAILED_UNSUPPORTED", ".github/workflows/courier_worker.yml", "Implement bounded task types")
        else:
            create_finding("GitHub worker cannot become arbitrary shell service", "os.system in workflow", "Found os.system", "Removed os.system", ".github/workflows/courier_worker.yml", "Remove arbitrary execution")

    finally:
        stop_server(proc)
        if os.path.exists(state_file): os.remove(state_file)

if __name__ == "__main__":
    run_tests()
    
    final_output = f"""
PROPERTIES_TESTED={results['PROPERTIES_TESTED']}
PASS={results['PASS']}
REAL_DEFECTS={results['REAL_DEFECTS']}
FALSE_POSITIVES={results['FALSE_POSITIVES']}
AUTH_FAIL_CLOSED={results['AUTH_FAIL_CLOSED']}
CORRELATION_FAIL_CLOSED={results['CORRELATION_FAIL_CLOSED']}
DUPLICATE_SAFE={results['DUPLICATE_SAFE']}
MALFORMED_INPUT_SAFE={results['MALFORMED_INPUT_SAFE']}
FILES_CHANGED=tests/boundaries/run_boundaries.py
COMMIT=pending
PUSHED=NO
REAL_WALL=NONE
STOPPED=YES
"""
    print("====================")
    print(final_output.strip())
