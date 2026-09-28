def test_workflow_plan_must_be_list(srv):
    resp = srv.app.test_client().post("/goals", headers={"X-Courier-Auth": "dummy-auth-key"}, json={"goal_text": "t", "workflow_plan": {"evil": "dict"}})
    assert resp.status_code == 400
    assert "must be a list" in resp.get_json()["error"]
