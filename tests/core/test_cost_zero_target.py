from courier_core.cost_transparency import derive_goal_cost_summary


def _target(target):
    goal = {
        "goal_id": "g",
        "workflow_plan": [{"task_id": "t", "target_agent": target}],
    }
    res = derive_goal_cost_summary(goal, {"tasks": {}, "workers": {}})
    step = res["provider_usage_breakdown"][0]
    return (
        res["payg_spend_triggered"],
        res["budget_firewall_status"],
        step["provider"],
        step["cost_class"],
    )


def test_numeric_zero_target_is_not_free():
    assert (
        _target(0),
        _target(False),
        _target(""),
        _target("local"),
    ) == (
        (True, "PAYG_TRIGGERED", "unknown", "unknown"),
        (True, "PAYG_TRIGGERED", "unknown", "unknown"),
        (True, "PAYG_TRIGGERED", "unknown", "unknown"),
        (False, "INTACT", "local", "free"),
    )
