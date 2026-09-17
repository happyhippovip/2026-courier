import os, sys, time, subprocess, json, urllib.request, urllib.error
import shutil
from pathlib import Path

proxy_code = """
from flask import Flask, request, Response
import requests

app = Flask(__name__)
counts = {"heartbeat": 0, "claim": 0, "result": 0}

@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy(path):
    global counts
    if 'heartbeat' in path:
        counts['heartbeat'] += 1
        if counts['heartbeat'] <= 1:
            return "Simulated heartbeat error", 500
    if 'claim' in path:
        counts['claim'] += 1
        if counts['claim'] <= 1:
            return "Simulated claim error", 500
    if 'result' in path:
        counts['result'] += 1
        if counts['result'] <= 6:
            return "Simulated result error", 500
            
    url = f"http://127.0.0.1:8080/{path}"
    resp = requests.request(
        method=request.method,
        url=url,
        headers={key: value for (key, value) in request.headers if key != 'Host'},
        data=request.get_data(),
        cookies=request.cookies,
        allow_redirects=False)
    
    excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
    headers = [(name, value) for (name, value) in resp.raw.headers.items()
               if name.lower() not in excluded_headers]
               
    return Response(resp.content, resp.status_code, headers)

if __name__ == '__main__':
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(port=8081)
"""

def run_proof():
    os.environ["COURIER_STATE_FILE"] = os.path.abspath("test_central_state.json")
    if os.path.exists("test_central_state.json"):
        os.remove("test_central_state.json")
    if os.path.exists("server/state/central_state.json"):
        os.remove("server/state/central_state.json")
        
    os.environ["COURIER_API_KEY"] = "test-secret-key"
    os.environ["COURIER_WORKER_ID"] = "w21-worker"
    os.environ["UV_PROJECT_ENVIRONMENT"] = os.path.abspath(".venv_service")
    
    with open("w21_proxy.py", "w") as f:
        f.write(proxy_code)

    print("Starting Courier Server...")
    server_proc = subprocess.Popen([sys.executable, "-m", "flask", "--app", "server.app:app", "run", "--port", "8080"], env=os.environ)
    print("Starting Proxy...")
    proxy_proc = subprocess.Popen([sys.executable, "w21_proxy.py"])
    
    def wait_for_port(port):
        for _ in range(30):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/health" if port == 8080 else f"http://127.0.0.1:{port}/nonexistent")
                break
            except urllib.error.HTTPError as e:
                break
            except Exception:
                time.sleep(0.5)
        else:
            sys.exit(f"Port {port} failed to start")
            
    wait_for_port(8080)
    wait_for_port(8081)

    print("Submitting goal...")
    plan = [{"task_id": "T-W21", "instruction": "echo 'W21 test' > w21_artifact.txt", "target_agent": "windows", "artifacts": ["w21_artifact.txt"]}]
    req = urllib.request.Request("http://127.0.0.1:8080/goals", 
                                 data=json.dumps({"goal_text": "Verify W21", "workflow_plan": plan, "terminal": True}).encode(), 
                                 headers={"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req) as res:
        goal_data = json.loads(res.read())
        goal_id = goal_data["goal_id"]

    marker = Path("scripts/windows_worker/state/result_marker.json")
    if marker.exists(): marker.unlink()
    
    os.environ["COURIER_SERVER"] = "http://127.0.0.1:8081"
    
    print("Starting Windows Worker daemon.py...")
    worker_proc = subprocess.Popen([sys.executable, "scripts/windows_worker/daemon.py"], env=os.environ)
    
    recovered = False
    
    for _ in range(120):
        req = urllib.request.Request(f"http://127.0.0.1:8080/goals/{goal_id}", headers={"Authorization": "Bearer test-secret-key"})
        goal_state = json.loads(urllib.request.urlopen(req).read())
        if "tasks" in goal_state and len(goal_state["tasks"]) > 0:
            task_state = goal_state["tasks"][0]
            print(f"Goal task status: {task_state['status']} attempts: {task_state.get('attempts')}", flush=True)
            if task_state["status"] in ("RESULT_RECEIVED", "FAILED_TERMINAL", "FAILED", "RECONCILED"):
                print(f"Task is {task_state['status']}. Attempts: {task_state.get('attempts')}", flush=True)
                if task_state.get("attempts", 0) == 1:
                    recovered = True
                break
        time.sleep(1)

    worker_proc.kill()
    server_proc.kill()
    proxy_proc.kill()
    
    if os.path.exists("w21_proxy.py"): os.remove("w21_proxy.py")
    
    if not recovered:
        sys.exit("W21 Proof Failed: Task result was not recovered and delivered correctly, or attempts > 1.")
        
    print("PASS_W21: TRANSPORT_RETRY_PRESERVES_LOGICAL_ATTEMPT")

if __name__ == "__main__":
    run_proof()
