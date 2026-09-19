import re

with open("tests/test_turbo_queue.py", "r") as f:
    content = f.read()

content = content.replace("def test_turbo_queue_parallel_ab_wait_c(app_state):", "def test_turbo_queue_parallel_fixture_state(app_state):")

new_test = """
def test_turbo_queue_integration_api_path(app_state):
    import server.app
    server.app.API_KEY = "test"
    server.app.VERIFIER_API_KEY = "test_verifier"
    
    auth_worker = {"Authorization": "Bearer test"}
    auth_verifier = {"Authorization": "Bearer test_verifier"}
    
    r1 = app_state.post("/workers/register", json={"worker_id": "w1", "capabilities": ["mock"]}, headers=auth_worker)
    assert r1.status_code == 200
    w1_id = "w1"
    
    r2 = app_state.post("/workers/register", json={"worker_id": "w2", "capabilities": ["mock"]}, headers=auth_worker)
    assert r2.status_code == 200
    w2_id = "w2"

    goal_data = {
        "goal_text": "Turbo API test",
        "workflow_plan": [
            {"task_id": "A2", "target_agent": "mock", "instruction": "Do A2"},
            {"task_id": "B2", "target_agent": "mock", "instruction": "Do B2"},
            {"task_id": "C2", "target_agent": "mock", "instruction": "Do C2", "depends_on": ["A2", "B2"]}
        ]
    }
    r = app_state.post("/goals", json=goal_data, headers=auth_worker)
    assert r.status_code == 200

    # Claim A2 and B2
    t1_res = app_state.post("/tasks/claim", json={"worker_id": w1_id}, headers=auth_worker)
    t1 = t1_res.json.get("task")
    t2_res = app_state.post("/tasks/claim", json={"worker_id": w2_id}, headers=auth_worker)
    t2 = t2_res.json.get("task")

    assert t1 is not None and t2 is not None
    assert set([t1["task_id"], t2["task_id"]]) == {"A2", "B2"}

    # Submit Result for t1
    result_A = {
        "goal_id": t1["goal_id"],
        "task_id": t1["task_id"],
        "attempt_id": t1["attempt_id"],
        "dispatch_id": t1["dispatch_id"],
        "execution_ref": t1["execution_ref"],
        "worker_id": w1_id,
        "run_id": "r1",
        "result_id": "res_A2",
        "status": "SUCCESS",
        "artifacts": []
    }
    r = app_state.post(f"/tasks/{t1['task_id']}/result", json=result_A, headers=auth_worker)
    assert r.status_code == 200

    # Submit Result for t2
    result_B = {
        "goal_id": t2["goal_id"],
        "task_id": t2["task_id"],
        "attempt_id": t2["attempt_id"],
        "dispatch_id": t2["dispatch_id"],
        "execution_ref": t2["execution_ref"],
        "worker_id": w2_id,
        "run_id": "r2",
        "result_id": "res_B2",
        "status": "SUCCESS",
        "artifacts": []
    }
    r = app_state.post(f"/tasks/{t2['task_id']}/result", json=result_B, headers=auth_worker)
    assert r.status_code == 200
    
    # Try an INVALID verify (using producer key instead of verifier key)
    verify_invalid_payload = {
        "task_id": t1["task_id"],
        "verifier_id": "v1",
        "result_id": "res_A2",
        "artifacts": [],
        "verdict": "PASS",
        "received_runtime_identity": t1.get("server_binding")
    }
    r = app_state.post(f"/tasks/{t1['task_id']}/verify", json=verify_invalid_payload, headers=auth_worker)
    assert r.status_code == 403
    assert "producer cannot certify itself" in r.json.get("error", "")

    # VALID verify for t1
    verify_valid_A = {
        "task_id": t1["task_id"],
        "verifier_id": "v1",
        "result_id": "res_A2",
        "artifacts": [],
        "verdict": "PASS",
        "received_runtime_identity": t1.get("server_binding")
    }
    r = app_state.post(f"/tasks/{t1['task_id']}/verify", json=verify_valid_A, headers=auth_verifier)
    assert r.status_code == 200
    
    # After A is verified, w1 asks for task. C should NOT be returned because B is not verified yet.
    r = app_state.post("/tasks/claim", json={"worker_id": w1_id}, headers=auth_worker)
    assert r.status_code == 200
    t3 = r.json.get("task")
    assert t3 is None, "C2 should wait for B2"
    
    # VALID verify for t2
    verify_valid_B = {
        "task_id": t2["task_id"],
        "verifier_id": "v2",
        "result_id": "res_B2",
        "artifacts": [],
        "verdict": "PASS",
        "received_runtime_identity": t2.get("server_binding")
    }
    r = app_state.post(f"/tasks/{t2['task_id']}/verify", json=verify_valid_B, headers=auth_verifier)
    assert r.status_code == 200
    
    # Now w1 can claim C
    r = app_state.post("/tasks/claim", json={"worker_id": w1_id}, headers=auth_worker)
    assert r.status_code == 200
    t_c = r.json.get("task")
    assert t_c is not None
    assert t_c["task_id"] == "C2"

"""

with open("tests/test_turbo_queue.py", "w") as f:
    f.write(content + "\n" + new_test)

