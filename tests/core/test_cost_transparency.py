"""Tests for Cost & Provider Transparency (User Acceptance Requirement 03)."""
import pytest

from courier_core.cost_transparency import (
    COST_CLASS_FREE,
    COST_CLASS_HIGH,
    COST_CLASS_LOW,
    COST_CLASS_MEDIUM,
    FIREWALL_INTACT,
    FIREWALL_TRIGGERED,
    describe_billing_mode,
    derive_goal_cost_summary,
)


def test_describe_billing_mode():
    assert describe_billing_mode(COST_CLASS_FREE, "local") == "Local Deterministic (FREE)"
    assert describe_billing_mode(COST_CLASS_LOW, "google") == "Google Subscription (INCLUDED)"
    assert describe_billing_mode(COST_CLASS_MEDIUM, "anthropic") == "Anthropic Subscription (INCLUDED)"
    assert describe_billing_mode(COST_CLASS_HIGH, "openai") == "Openai Metered (PAYG)"
    assert describe_billing_mode(None, None) == "Local Deterministic (FREE)"


def test_bool_billing_mode_is_not_free():
    seen = []
    for flag in (False, True):
        try:
            text = describe_billing_mode(flag, "local")
        except Exception as exc:
            seen.append((flag, type(exc).__name__, str(exc)))
        else:
            seen.append((flag, "accepted", text))
    assert seen == [
        (False, "accepted", "Local (UNKNOWN)"),
        (True, "accepted", "Local (UNKNOWN)"),
    ], seen


def test_derive_goal_cost_summary_empty():
    res = derive_goal_cost_summary(None, None)
    assert res["payg_spend_triggered"] is False
    assert res["budget_firewall_status"] == FIREWALL_INTACT
    assert res["total_steps"] == 0
    assert len(res["provider_usage_breakdown"]) == 0


def test_derive_goal_cost_summary_zero_spend_guarantee():
    goal = {
        "goal_id": "goal-zero",
        "workflow_plan": [
            {
                "task_id": "task-1",
                "instruction": "Parse local files",
                "target_agent": "mac",
                "worker_id": "worker-mac-1",
            },
            {
                "task_id": "task-2",
                "instruction": "Index documents with free model",
                "target_agent": "linux",
                "worker_id": "worker-cli-1",
            },
            {
                "task_id": "task-3",
                "instruction": "Run verifier check",
                "target_agent": "verifier",
                "worker_id": "worker-verifier-1",
            },
        ],
    }
    state = {
        "tasks": {
            "task-1": {"worker_id": "worker-mac-1"},
            "task-2": {"worker_id": "worker-cli-1"},
            "task-3": {"worker_id": "worker-verifier-1"},
        },
        "workers": {
            "worker-mac-1": {"cost_class": "free", "provider": "local"},
            "worker-cli-1": {"cost_class": "low", "provider": "google"},
            "worker-verifier-1": {"cost_class": "free", "provider": "local"},
        },
    }

    res = derive_goal_cost_summary(goal, state)
    assert res["payg_spend_triggered"] is False
    assert res["budget_firewall_status"] == FIREWALL_INTACT
    assert res["total_steps"] == 3
    assert res["steps_free"] == 2
    assert res["steps_included"] == 1
    assert res["steps_payg"] == 0
    assert "0.00 EUR" in res["estimated_marginal_cost"]
    assert "100% Zero-Spend Guaranteed" in res["human_summary"]

    breakdown = res["provider_usage_breakdown"]
    assert len(breakdown) == 3
    assert breakdown[0]["billing_mode"] == "Local Deterministic (FREE)"
    assert breakdown[1]["billing_mode"] == "Google Subscription (INCLUDED)"
    assert breakdown[2]["billing_mode"] == "Local Deterministic (FREE)"


def test_derive_goal_cost_summary_with_payg_detection():
    goal = {
        "goal_id": "goal-payg",
        "workflow_plan": [
            {
                "task_id": "task-prep",
                "instruction": "Prep data",
                "worker_id": "worker-local",
            },
            {
                "task_id": "task-heavy",
                "instruction": "Call expensive cloud API",
                "worker_id": "worker-cloud",
            },
        ],
    }
    state = {
        "tasks": {
            "task-prep": {"worker_id": "worker-local"},
            "task-heavy": {"worker_id": "worker-cloud"},
        },
        "workers": {
            "worker-local": {"cost_class": "free", "provider": "local"},
            "worker-cloud": {"cost_class": "high", "provider": "openai"},
        },
    }

    res = derive_goal_cost_summary(goal, state)
    assert res["payg_spend_triggered"] is True
    assert res["budget_firewall_status"] == FIREWALL_TRIGGERED
    assert res["total_steps"] == 2
    assert res["steps_free"] == 1
    assert res["steps_included"] == 0
    assert res["steps_payg"] == 1
    assert "Metered PAYG" in res["estimated_marginal_cost"]
    assert "financial budget firewall recorded" in res["human_summary"].lower()


def test_unknown_cost_class_triggers_firewall_fail_closed():
    goal = {
        "goal_id": "goal-unknown-cost",
        "workflow_plan": [
            {"task_id": "task-unclassified", "instruction": "Run external step", "worker_id": "w-unknown"}
        ],
    }
    state = {
        "tasks": {"task-unclassified": {"worker_id": "w-unknown"}},
        "workers": {"w-unknown": {"cost_class": "unknown", "provider": "external_api"}},
    }
    res = derive_goal_cost_summary(goal, state)
    assert res["payg_spend_triggered"] is True
    assert res["budget_firewall_status"] == FIREWALL_TRIGGERED
    assert res["steps_free"] == 0
    assert res["steps_payg"] == 1


def test_server_goal_cost_endpoint(tmp_path, monkeypatch):
    """Test Flask endpoint /goals/<goal_id>/cost."""
    import server.app as courier_server

    monkeypatch.setattr(courier_server, "STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setattr(courier_server, "API_KEY", "test-secret")
    app = courier_server.app
    client = app.test_client()
    headers = {"Authorization": "Bearer test-secret"}

    goal_id = "test-cost-goal"
    state = {
        "goals": {
            goal_id: {
                "goal_id": goal_id,
                "status": "ACTIVE",
                "workflow_plan": [
                    {
                        "task_id": "t-1",
                        "instruction": "Step 1",
                        "target_agent": "mac",
                    }
                ],
            }
        },
        "tasks": {},
        "workers": {},
    }
    courier_server.save_state(state)

    res = client.get(f"/goals/{goal_id}/cost", headers=headers)
    assert res.status_code == 200
    data = res.get_json()
    assert data["payg_spend_triggered"] is False
    assert data["budget_firewall_status"] == FIREWALL_INTACT
    assert data["total_steps"] == 1

    res_404 = client.get("/goals/nonexistent-goal-id/cost", headers=headers)
    assert res_404.status_code == 404



# --- REDTEAM R1 negative test --------------------------------------------
def test_unknown_provider_without_cost_class_is_not_zero_spend():
    goal = {"goal_id": "g", "workflow_plan": [{"task_id": "t1", "target_agent": "openai-api-gpt"}]}
    s = derive_goal_cost_summary(goal, {"tasks": {}, "workers": {}})
    assert s["budget_firewall_status"] != "INTACT"
    assert "Zero-Spend" not in s["human_summary"]


def test_bool_cost_class_is_not_free():
    goal = {
        "goal_id": "g",
        "workflow_plan": [{"task_id": "task-1", "instruction": "local", "target_agent": "local"}],
    }
    seen = []
    for flag in (False, True):
        state = {
            "tasks": {"task-1": {"worker_id": "w"}},
            "workers": {"w": {"provider": "local", "cost_class": flag}},
        }
        res = derive_goal_cost_summary(goal, state)
        seen.append((
            flag,
            res["steps_free"],
            res["steps_payg"],
            res["payg_spend_triggered"],
            res["estimated_marginal_cost"],
            res["provider_usage_breakdown"][0]["cost_class"],
        ))
    assert seen == [
        (False, 0, 1, True, "Metered PAYG (Check provider credit consumption)", "unknown"),
        (True, 0, 1, True, "Metered PAYG (Check provider credit consumption)", "unknown"),
    ], seen
