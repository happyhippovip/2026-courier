def test_manual_plan_target_agent_normalization(srv):
    http = srv.app.test_client()
    from tests.test_p3_server_idempotency import WORKER
    # manual plan
    http.post("/goals", headers=WORKER, json={
        "goal_text": "foo", 
        "workflow_plan": [{"task_id": "t1", "target_agent": "codex", "instruction": "echo hi"}]
    })
    
    # register windows worker
    http.post("/workers/register", headers=WORKER, json={"worker_id": "W1", "capabilities": ["windows"]})
    
    # attempt claim
    res = http.post("/tasks/claim", headers=WORKER, json={"worker_id": "W1"}).get_json()
    assert res.get("task") is not None, res
