def test_prepare_task_capability_bug(srv):
    http = srv.app.test_client()
    from tests.test_p3_server_idempotency import WORKER
    # manual plan
    http.post("/goals", headers=WORKER, json={
        "goal_text": "foo", 
        "workflow_plan": [{"task_id": "t1", "target_agent": "mac", "instruction": "echo hi"}]
    })
    
    # register mac worker
    http.post("/workers/register", headers=WORKER, json={"worker_id": "M1", "capabilities": ["macos"]})
    
    # attempt claim
    res = http.post("/tasks/claim", headers=WORKER, json={"worker_id": "M1"})
    print("STATUS:", res.status_code)
    print("BODY:", res.get_json())
    assert res.status_code == 200, res.get_json()
    assert res.get_json().get("task") is not None
