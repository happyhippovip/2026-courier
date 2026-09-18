import json, requests, os, sys, uuid

API_URL = os.environ.get("COURIER_SERVER", "http://127.0.0.1:8080")
try:
    with open("server/config.json", "r") as f:
        API_KEY = json.load(f).get("API_KEY", "test-key-12345")
except:
    API_KEY = "test-key-12345"

HEADERS = {"Authorization": f"Bearer {API_KEY}"}

def main():
    print("Preparing Physical Acceptance Goal...")
    goal_id = f"physical-proof-{uuid.uuid4().hex[:8]}"
    
    plan = [
        {"task_id": f"pt-01", "target_agent": "mac", "mode": "NATIVE", "instruction": "echo 'Mac Native Task 1'"},
        {"task_id": f"pt-02", "depends_on": "pt-01", "target_agent": "windows", "mode": "NATIVE", "instruction": "echo Windows Native Task 2"},
        {"task_id": f"pt-03", "depends_on": "pt-02", "target_agent": "mac", "mode": "NATIVE", "instruction": "echo 'Mac Native Task 3'"},
        {"task_id": f"pt-04", "depends_on": "pt-03", "target_agent": "windows", "mode": "NATIVE", "instruction": "echo Windows Native Task 4"},
        
        # WAITING_PROVIDER SCENARIOS
        {"task_id": f"pt-05", "depends_on": "pt-04", "target_agent": "mac", "mode": "NATIVE", "instruction": "echo 'quota exceeded'"},
        {"task_id": f"pt-06", "depends_on": "pt-05", "target_agent": "windows", "mode": "NATIVE", "instruction": "echo quota exceeded"},
        
        # RESTART/RESUME SCENARIOS (AMBIGUOUS CRASH)
        # We will use python to kill the parent daemon process to test survival.
        {"task_id": f"pt-07", "depends_on": "pt-06", "target_agent": "mac", "mode": "NATIVE", "instruction": "python3 -c \"import os, signal; os.kill(os.getppid(), signal.SIGKILL)\""},
        {"task_id": f"pt-08", "depends_on": "pt-07", "target_agent": "windows", "mode": "NATIVE", "instruction": "python -c \"import os, subprocess; subprocess.run(['taskkill', '/F', '/PID', str(os.getppid())])\""},
        
        # FINAL TASKS
        {"task_id": f"pt-09", "depends_on": "pt-08", "target_agent": "mac", "mode": "NATIVE", "instruction": "echo 'Mac Native Task 9'"},
        {"task_id": f"pt-10", "depends_on": "pt-09", "target_agent": "windows", "mode": "NATIVE", "instruction": "echo Windows Native Task 10"}
    ]
    
    payload = {
        "goal_text": "Physical Acceptance Proof Run",
        "workflow_plan": plan
    }
    
    res = requests.post(f"{API_URL}/goals", json=payload, headers=HEADERS)
    if res.status_code == 200:
        print(f"Successfully injected Physical Acceptance Goal: {res.json().get('goal_id')}")
        print("Run the server, start Mac daemon, start Windows daemon, and monitor.")
    else:
        print(f"Failed to inject goal. Is server running? Error: {res.text}")

if __name__ == '__main__':
    main()
