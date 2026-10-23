from courier_core.cost_transparency import derive_goal_cost_summary


def _class(cost_class, present=True):
    step = {"task_id": "t", "target_agent": "local"}
    if present:
        step["cost_class"] = cost_class
    goal = {"goal_id": "g", "workflow_plan": [step]}
    res = derive_goal_cost_summary(goal, {"tasks": {}, "workers": {}})
    card = res["provider_usage_breakdown"][0]
    return (
        res["payg_spend_triggered"],
        res["budget_firewall_status"],
        card["cost_class"],
    )


def test_a_step_cost_class_is_not_dropped():
    assert (
        _class("high"),
        _class(0),
        _class(None, present=False),
    ) == (
        (True, "PAYG_TRIGGERED", "high"),
        (True, "PAYG_TRIGGERED", "unknown"),
        (False, "INTACT", "free"),
    )
