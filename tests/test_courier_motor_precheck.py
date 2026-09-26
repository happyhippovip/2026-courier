from scripts.courier_motor_precheck import has_dispatchable_work


def state(step_status="QUEUED", target="github", goal_status="ACTIVE", index=0, workers=None):
    return {"goals": {"g1": {"status": goal_status, "current_step_index": index,
                             "workflow_plan": [{"task_id": "t1", "status": step_status, "target_agent": target, "goal_id": "g1", "target_capability": "github" if "github" in target.lower() else "mac" if "mac" in target.lower() else "windows" if "windows" in target.lower() else "linux"}]}},
            "tasks": {}, "workers": workers or {}}


def test_queued_github_step_is_work():
    assert has_dispatchable_work(state())
    assert has_dispatchable_work(state(target="GitHub-Hosted"))


def test_idle_states_are_not_work():
    assert not has_dispatchable_work({})
    assert not has_dispatchable_work(state(step_status="DISPATCHED"))
    assert not has_dispatchable_work(state(target="windows"))
    assert not has_dispatchable_work(state(goal_status="DONE"))
    assert not has_dispatchable_work(state(index=1))


def test_busy_dispatcher_is_not_work():
    busy = {"GITHUB-DISPATCHER": {"current_task": "t0"}}
    assert not has_dispatchable_work(state(workers=busy))

def test_precheck_parity_with_server_claim_task(monkeypatch):
    import server.app
    from server.app import claim_task
    
    fixtures = [
        state(),
        state(target="GitHub-Hosted"),
        {"goals": {}, "tasks": {}, "workers": {}},
        state(step_status="DISPATCHED"),
        state(target="windows"),
        state(goal_status="DONE"),
        state(index=1),
        state(workers={"GITHUB-DISPATCHER": {"current_task": "t0"}}),
    ]
    
    for fixture in fixtures:
        precheck_claims = has_dispatchable_work(fixture)
        
        if "GITHUB-DISPATCHER" not in fixture.setdefault("workers", {}):
            fixture["workers"]["GITHUB-DISPATCHER"] = {
                "available": True,
                "capabilities": ["github", "linux"],
                "cost_class": "free"
            }
        else:
            fixture["workers"]["GITHUB-DISPATCHER"].update({
                "available": True,
                "capabilities": ["github", "linux"],
                "cost_class": "free"
            })
            
        monkeypatch.setattr(server.app, "load_state", lambda: fixture)
        monkeypatch.setattr(server.app, "save_state", lambda x: None)
        
        class MockRequest:
            def __init__(self):
                self.headers = {"Authorization": f"Bearer {server.app.API_KEY}"}
            def get_json(self, silent=True):
                return {"worker_id": "GITHUB-DISPATCHER"}
        
        monkeypatch.setattr(server.app, "request", MockRequest())
        
        with server.app.app.app_context():
            res = claim_task()
            
        task_data = res.json if hasattr(res, "json") else res[0].json
        server_claims = task_data.get("task") is not None
        assert precheck_claims == server_claims, f"Parity mismatch: precheck={precheck_claims}, server={server_claims}, task_data={task_data}"
