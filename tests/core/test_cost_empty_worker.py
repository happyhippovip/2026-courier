from courier_core.cost_transparency import derive_goal_cost_summary


def _card(include_worker):
    step = {"task_id": "t", "target_agent": "local"}
    workers = {}
    if include_worker:
        step["worker_id"] = "w"
        workers["w"] = {}
    goal = {"goal_id": "g", "workflow_plan": [step]}
    res = derive_goal_cost_summary(goal, {"tasks": {}, "workers": workers})
    card = res["provider_usage_breakdown"][0]
    return (
        res["payg_spend_triggered"],
        res["budget_firewall_status"],
        card["provider"],
        card["cost_class"],
    )


def test_an_empty_worker_record_is_not_free():
    assert (
        _card(True),
        _card(False),
    ) == (
        (True, "PAYG_TRIGGERED", "unknown", "unknown"),
        (False, "INTACT", "local", "free"),
    )
