from courier_core.cost_transparency import derive_goal_cost_summary


def _worker(worker_id):
    step = {"task_id": "t", "target_agent": "local"}
    if worker_id is not None:
        step["worker_id"] = worker_id
    goal = {"goal_id": "g", "workflow_plan": [step]}
    res = derive_goal_cost_summary(goal, {"tasks": {}, "workers": {}})
    card = res["provider_usage_breakdown"][0]
    return (
        res["payg_spend_triggered"],
        res["budget_firewall_status"],
        card["provider"],
        card["cost_class"],
    )


def test_a_missing_worker_is_not_free():
    assert (
        _worker("ghost"),
        _worker(None),
    ) == (
        (True, "PAYG_TRIGGERED", "unknown", "unknown"),
        (False, "INTACT", "local", "free"),
    )
