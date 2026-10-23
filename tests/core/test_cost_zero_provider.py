from courier_core.cost_transparency import derive_goal_cost_summary


def _card(provider):
    goal = {
        "goal_id": "g",
        "workflow_plan": [{"task_id": "task-1", "instruction": "local", "target_agent": "local"}],
    }
    state = {
        "tasks": {"task-1": {"worker_id": "w"}},
        "workers": {"w": {"provider": provider, "cost_class": "free"}},
    }
    res = derive_goal_cost_summary(goal, state)
    row = res["provider_usage_breakdown"][0]
    return (
        res["steps_free"],
        res["payg_spend_triggered"],
        row["provider"],
        row["cost_class"],
    )


def test_numeric_zero_provider_is_not_local_free():
    assert (
        _card(0),
        _card("local"),
    ) == (
        (0, True, "unknown", "unknown"),
        (1, False, "local", "free"),
    )
