from courier_core.cost_transparency import derive_goal_cost_summary


def _card(cost_class):
    goal = {
        "goal_id": "g",
        "workflow_plan": [{"task_id": "task-1", "instruction": "local", "target_agent": "local"}],
    }
    state = {
        "tasks": {"task-1": {"worker_id": "w"}},
        "workers": {"w": {"provider": "local", "cost_class": cost_class}},
    }
    res = derive_goal_cost_summary(goal, state)
    return (
        res["steps_free"],
        res["payg_spend_triggered"],
        res["provider_usage_breakdown"][0]["cost_class"],
    )


def test_numeric_zero_cost_class_is_not_free():
    assert (
        _card(0),
        _card("free"),
    ) == (
        (0, True, "unknown"),
        (1, False, "free"),
    )
