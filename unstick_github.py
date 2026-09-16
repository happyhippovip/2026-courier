import requests, os

API_KEY = os.environ.get("COURIER_API_KEY")
if not API_KEY:
    import subprocess
    API_KEY = subprocess.check_output(["security", "find-generic-password", "-a", "courier_worker", "-s", "courier_api_key", "-w"]).decode().strip()

HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# Read central state to get exact fields
import json
with open("server/state/central_state.json") as f:
    state = json.load(f)

# Find the stuck task in GITHUB-DISPATCHER
worker = state.get("workers", {}).get("GITHUB-DISPATCHER")
tid = worker.get("current_task")
if tid:
    print(f"Unsticking {tid}...")
    t = state["tasks"][tid]
    
    payload = {
        "worker_id": "GITHUB-DISPATCHER",
        "goal_id": t["goal_id"],
        "task_id": tid,
        "dispatch_id": t["dispatch_id"],
        "attempt_id": t["attempt_id"],
        "run_id": "manual-unstick",
        "result_id": "manual-unstick",
        "status": "FAILED",
        "artifacts": [],
        "raw_result": {"status": "FAILED", "reason": "VALIDATION_ERROR"}
    }
    r = requests.post("http://localhost:8080/tasks/result", json=payload, headers=HEADERS)
    print(r.status_code, r.text)

