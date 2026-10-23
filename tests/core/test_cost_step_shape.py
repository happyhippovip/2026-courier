from courier_core.cost_transparency import derive_goal_cost_summary


def _steps(plan):
    goal = {"goal_id": "g", "workflow_plan": plan}
    try:
        res = derive_goal_cost_summary(goal, {"tasks": {}, "workers": {}})
    except Exception as exc:
        return ("crashed", type(exc).__name__, None, None)
    return (
        res["payg_spend_triggered"],
        res["budget_firewall_status"],
        res["total_steps"],
        "Zero-Spend" in res["human_summary"],
    )


def test_a_non_dict_step_is_not_zero_spend():
    assert (
        _steps(["local"]),
        _steps([{"task_id": "t", "target_agent": "local"}]),
    ) == (
        (True, "PAYG_TRIGGERED", 1, False),
        (False, "INTACT", 1, True),
    )
