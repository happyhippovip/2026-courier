from scripts.courier_motor_precheck import has_dispatchable_work


def state(step_status="QUEUED", target="github", goal_status="ACTIVE", index=0, workers=None):
    return {"goals": {"g1": {"status": goal_status, "current_step_index": index,
                             "workflow_plan": [{"task_id": "t1", "status": step_status, "target_agent": target}]}},
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
