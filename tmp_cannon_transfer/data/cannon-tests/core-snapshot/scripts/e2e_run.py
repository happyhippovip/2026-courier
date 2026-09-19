import os
import sys
import time
import subprocess
import json
import uuid
import tempfile
import urllib.request
import urllib.error

def request(method, path, data=None):
    url = f"http://127.0.0.1:8088{path}"
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", "Bearer dummy-api-key")
    if data:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(data).encode("utf-8")
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode()), response.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode()), e.code
    except urllib.error.URLError:
        return None, 500

def wait_for_server():
    for _ in range(30):
        res, code = request("GET", "/status")
        if res: return True
        time.sleep(0.5)
    return False

def main():
    env = os.environ.copy()
    env["COURIER_API_KEY"] = "dummy-api-key"
    env["COURIER_VERIFIER_API_KEY"] = "test-verifier-key"
    env["DISABLE_KEYRING"] = "1"
    env["PYTEST_CURRENT_TEST"] = "e2e_run"
    env["FLASK_APP"] = "server.app"
    tmp_state = os.path.join(tempfile.gettempdir(), f"state_{uuid.uuid4().hex}.json")
    env["STATE_FILE"] = tmp_state
    env["COURIER_SERVER"] = "http://127.0.0.1:8088"

    print("Starting server...")
    server = subprocess.Popen(["uv", "run", "python", "-m", "flask", "run", "--port", "8088"], env=env, stdout=sys.stdout, stderr=sys.stderr)
    
    # Let's also verify wait_for_server() doesn't falsely succeed on 401
    def wait_for_server():
        for _ in range(30):
            res, code = request("GET", "/status")
            if code == 200: return True
            time.sleep(0.5)
        return False
    
    if not wait_for_server():
        print("Server failed to start")
        server.terminate()
        return

    print("Starting Windows worker...")
    env_win = env.copy()
    env_win["COURIER_WORKER_ID"] = "WIN-01"
    win_db = os.path.join(tempfile.gettempdir(), f"win_db_{uuid.uuid4().hex}.sqlite")
    env_win["COURIER_DB_PATH"] = win_db
    win_worker = subprocess.Popen(["uv", "run", "python", "scripts/windows_worker/daemon.py"], env=env_win, stdout=sys.stdout, stderr=sys.stderr)

    print("Starting Mac worker...")
    env_mac = env.copy()
    env_mac["COURIER_WORKER_ID"] = "MAC-01"
    mac_db = os.path.join(tempfile.gettempdir(), f"mac_db_{uuid.uuid4().hex}.sqlite")
    env_mac["COURIER_DB_PATH"] = mac_db
    mac_worker = subprocess.Popen(["uv", "run", "python", "scripts/mac_worker/daemon.py"], env=env_mac, stdout=sys.stdout, stderr=sys.stderr)

    time.sleep(5) # Let them register and heartbeat

    workers, _ = request("GET", "/workers")
    
    win_ok = "WIN-01" in workers and workers.get("WIN-01", {}).get("available")
    mac_ok = "MAC-01" in workers and workers.get("MAC-01", {}).get("available")

    # Submit a goal with one WIN task, one MAC task, one HUMAN task
    goal_data = {
        "goal_text": "e2e test goal",
        "workflow_plan": [
            {"task_id": "t1", "target_agent": "windows", "instruction": "echo WIN_DONE"},
            {"task_id": "t2", "target_agent": "mac", "instruction": "echo MAC_DONE"},
            {"task_id": "t3", "target_agent": "chief", "instruction": "human review"}
        ]
    }
    goal_res, code = request("POST", "/goals", data=goal_data)
    goal_id = goal_res.get("goal_id")
    
    time.sleep(10) # Let tasks execute
    
    goal_state, _ = request("GET", f"/goals/{goal_id}")
    
    # Analyze
    tasks = {t["task_id"]: t for t in goal_state.get("tasks", [])}
    t1_done = tasks.get("t1", {}).get("status") in ["DONE", "PENDING_VERIFICATION"]
    t2_done = tasks.get("t2", {}).get("status") in ["DONE", "PENDING_VERIFICATION"]
    t3_human = tasks.get("t3", {}).get("status") == "HUMAN_REQUIRED"
    
    print(f"WIN OK: {win_ok}")
    print(f"MAC OK: {mac_ok}")
    print(f"T1 DONE: {t1_done}")
    print(f"T2 DONE: {t2_done}")
    print(f"T3 HUMAN: {t3_human}")

    # Clean up
    win_worker.terminate()
    mac_worker.terminate()
    server.terminate()
    
    win_worker.wait()
    mac_worker.wait()
    server.wait()

    print("Test finished.")

if __name__ == "__main__":
    main()
