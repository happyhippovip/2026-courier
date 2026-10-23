from courier_core.cost_transparency import derive_goal_cost_summary


def _plan(value, present=True):
    goal = {"goal_id": "g"}
    if present:
        goal["workflow_plan"] = value
    res = derive_goal_cost_summary(goal, {"tasks": {}, "workers": {}})
    return (
        res["payg_spend_triggered"],
        res["budget_firewall_status"],
        res["total_steps"],
        "Zero-Spend" in res["human_summary"],
    )


def test_a_non_list_plan_is_not_zero_spend():
    assert (
        _plan(None),
        _plan("step"),
        _plan(None, present=False),
    ) == (
        (True, "PAYG_TRIGGERED", 1, False),
        (True, "PAYG_TRIGGERED", 1, False),
        (False, "INTACT", 0, True),
    )
