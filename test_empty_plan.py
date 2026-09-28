def test_empty_workflow_plan_is_rejected(srv):
    http = srv.app.test_client()
    from tests.test_p3_server_idempotency import WORKER
    resp = http.post("/goals", headers=WORKER, json={"goal_text": "t", "workflow_plan": []})
    assert resp.status_code == 400
    assert "empty" in resp.get_json()["error"].lower()
