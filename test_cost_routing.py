import time
def test_cost_routing(srv):
    http = srv.app.test_client()
    # add goal
    goal = http.post("/goals", headers={"Authorization": "Bearer x"}, json={"goal_text": "foo", "workflow_plan": [{"task_id": "t1", "target_agent": "mac"}]}).get_json()
    
    # register high cost worker
    http.post("/workers/register", headers={"Authorization": "Bearer x"}, json={"worker_id": "HIGH", "capabilities": ["macos"], "cost_class": "high"})
    
    # register low cost worker
    http.post("/workers/register", headers={"Authorization": "Bearer x"}, json={"worker_id": "LOW", "capabilities": ["macos"], "cost_class": "low"})
    
    # claim with HIGH
    res = http.post("/tasks/claim", headers={"Authorization": "Bearer x"}, json={"worker_id": "HIGH"}).get_json()
    assert res["task"] is None, res
    
    # claim with LOW
    res2 = http.post("/tasks/claim", headers={"Authorization": "Bearer x"}, json={"worker_id": "LOW"}).get_json()
    assert res2["task"]["task_id"] == "t1", res2
