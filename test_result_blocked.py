def test_worker_failure_blocks_goal(srv):
    http = srv.app.test_client()
    from tests.test_p3_server_idempotency import WORKER, durable_result
    
    # 1. Create goal
    resp = http.post("/goals", headers=WORKER, json={
        "goal_text": "t", 
        "workflow_plan": [{"task_id": "t1", "instruction": "do it", "target_agent": "linux"}]
    })
    goal_id = resp.get_json()["goal_id"]
    
    # 2. Register & claim
    http.post("/workers/register", headers=WORKER, json={"worker_id": "W1", "capabilities": ["linux"]})
    claim = http.post("/tasks/claim", headers=WORKER, json={"worker_id": "W1"}).get_json()
    task = claim["task"]
    
    # 3. Report failure
    result = durable_result(task)
    result["status"] = "FAILED"
    result["artifacts"] = []
    
    http.post("/tasks/result", headers=WORKER, json=result)
    
    # 4. Check walls
    walls = http.get("/walls", headers=WORKER).get_json()
    assert goal_id in walls, f"Goal {goal_id} was not BLOCKED when worker reported failure!"
