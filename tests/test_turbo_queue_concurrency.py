from scripts.integration_contract import _canonical_hash
import pytest
import tempfile
import threading
import time
import requests
from pathlib import Path
from werkzeug.serving import make_server

class ServerThread(threading.Thread):
    def __init__(self, app):
        threading.Thread.__init__(self)
        self.server = make_server('localhost', 0, app)
        self.ctx = app.app_context()
        self.ctx.push()
        self.port = self.server.port

    def run(self):
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()
        self.ctx.pop()

@pytest.fixture
def test_server(monkeypatch):
    import server.app
    for k in ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"]:
        monkeypatch.delenv(k, raising=False)
    temp_dir = tempfile.mkdtemp()
    state_file = Path(temp_dir) / "central_state.json"
    monkeypatch.setattr(server.app, "STATE_FILE", str(state_file))
    monkeypatch.setattr(server.app, "API_KEY", "test")
    monkeypatch.setattr(server.app, "VERIFIER_API_KEY", "test_verifier")

    
    server_thread = ServerThread(server.app.app)
    server_thread.start()
    
    # Wait for server to be responsive
    base_url = f"http://localhost:{server_thread.port}"
    for _ in range(10):
        try:
            requests.get(base_url)
            break
        except requests.exceptions.ConnectionError:
            time.sleep(0.1)
            
    yield base_url
    
    server_thread.shutdown()
    server_thread.join()

def test_claim_race_one_task(test_server):
    auth = {"Authorization": "Bearer test"}
    requests.post(f"{test_server}/workers/register", json={"worker_id": "w1", "capabilities": ["mock"]}, headers=auth)
    requests.post(f"{test_server}/workers/register", json={"worker_id": "w2", "capabilities": ["mock"]}, headers=auth)
    
    requests.post(f"{test_server}/goals", json={
        "goal_text": "Race test",
        "workflow_plan": [{"task_id": "T1", "target_agent": "mock", "instruction": "Do"}]
    }, headers=auth)

    barrier = threading.Barrier(2)
    results = []

    def claimer(w_id):
        barrier.wait(timeout=5.0)
        res = requests.post(f"{test_server}/tasks/claim", json={"worker_id": w_id}, headers=auth)
        results.append((w_id, res.json().get("task")))

    t1 = threading.Thread(target=claimer, args=("w1",))
    t2 = threading.Thread(target=claimer, args=("w2",))
    t1.start(); t2.start()
    t1.join(); t2.join()

    # Exactly one should have the task, the other None
    tasks_claimed = [r[1] for r in results if r[1] is not None]
    assert len(tasks_claimed) == 1
    assert tasks_claimed[0]["task_id"] == "T1"

def test_concurrency_overlap_and_auto_continue(test_server):
    auth_worker = {"Authorization": "Bearer test"}
    auth_verifier = {"Authorization": "Bearer test_verifier"}
    requests.post(f"{test_server}/workers/register", json={"worker_id": "w1", "capabilities": ["mock"]}, headers=auth_worker)
    requests.post(f"{test_server}/workers/register", json={"worker_id": "w2", "capabilities": ["mock"]}, headers=auth_worker)
    
    requests.post(f"{test_server}/goals", json={
        "goal_text": "Overlap test",
        "workflow_plan": [
            {"task_id": "A", "target_agent": "mock", "instruction": "Do A"},
            {"task_id": "B", "target_agent": "mock", "instruction": "Do B"},
            {"task_id": "C", "target_agent": "mock", "instruction": "Do C", "depends_on": ["A", "B"]}
        ]
    }, headers=auth_worker)

    execution_barrier = threading.Barrier(2)
    completion_events = {"A": threading.Event(), "B": threading.Event(), "C": threading.Event()}
    
    exec_times = {}
    thread_res_ids = {}
    stop_event = threading.Event()

    def worker_loop(w_id):
        while not stop_event.is_set():
            res = requests.post(f"{test_server}/tasks/claim", json={"worker_id": w_id}, headers=auth_worker)
            task = res.json().get("task")
            if task:
                tid = task["task_id"]
                exec_times[tid] = time.time()
                
                # If A or B, wait at the barrier to prove execution overlap
                if tid in ("A", "B"):
                    execution_barrier.wait(timeout=5.0)
                

                import server.app, hashlib, json
                base_res = {
                    "goal_id": task["goal_id"], "task_id": tid, "attempt_id": task["attempt_id"],
                    "dispatch_id": task["dispatch_id"], "execution_ref": task["execution_ref"],
                    "worker_id": w_id, "run_id": f"run_{tid}",
                    "status": "SUCCESS", "artifacts": [],
                    "runtime_identity": server.app.SERVER_BINDING
                }
                rid = hashlib.sha256(json.dumps(base_res, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                result = dict(base_res, result_id=f"result-{rid}")

                requests.post(f"{test_server}/tasks/result", json=result, headers=auth_worker)
                thread_res_ids[tid] = result["result_id"]
                completion_events[tid].set()
            else:
                time.sleep(0.1)

    t1 = threading.Thread(target=worker_loop, args=("w1",))
    t2 = threading.Thread(target=worker_loop, args=("w2",))
    t1.start(); t2.start()

    # Wait for A and B to complete (meaning they both hit the barrier and submitted results)
    assert completion_events["A"].wait(timeout=5.0)
    assert completion_events["B"].wait(timeout=5.0)
    
    # Prove they overlapped
    assert "A" in exec_times and "B" in exec_times
    
    time.sleep(0.5)
    assert not completion_events["C"].is_set()
    
    # Verify A and B to unlock C
    import server.app
    state = server.app.load_state()
    for tid in ("A", "B"):
        t_data = state["tasks"][tid]
        requests.post(f"{test_server}/tasks/verify", json={
            "task_id": tid, "verifier_id": "v1", "result_id": thread_res_ids[tid],
            "artifacts": [], "verdict": "PASS", "received_runtime_identity": t_data.get("server_binding")
        }, headers=auth_verifier)
    
    # Duplicate verify shouldn't double-schedule
    requests.post(f"{test_server}/tasks/verify", json={
        "task_id": "A", "verifier_id": "v1", "result_id": thread_res_ids["A"],
        "artifacts": [], "verdict": "PASS", "received_runtime_identity": state["tasks"]["A"].get("server_binding")
    }, headers=auth_verifier)

    # Now the worker loops should automatically claim and finish C
    assert completion_events["C"].wait(timeout=5.0)
    
    stop_event.set()
    t1.join(); t2.join()

