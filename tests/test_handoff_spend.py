"""The shared handoff decision. CostGate is the only policy."""

import pytest

from scripts.handoff_spend import handoff_spend_block, marked_unknown_cost, spend_body_from_parked


def test_missing_estimate_stays_unknown():
    assert handoff_spend_block({}) == "UNKNOWN_COST"
    assert handoff_spend_block({"params": {"unit": "a"}}) == "UNKNOWN_COST"
    assert handoff_spend_block(None) == "UNKNOWN_COST"
    assert marked_unknown_cost("nope") is True


def test_unknown_marks_block_beside_an_explicit_zero():
    assert handoff_spend_block({"estimated_cost_eur": 0.0, "unknown_cost": True}) == "UNKNOWN_COST"
    assert handoff_spend_block({"estimated_cost_eur": 0.0, "cost_class": "unknown"}) == "UNKNOWN_COST"
    assert handoff_spend_block({
        "estimated_cost_eur": 0.0,
        "params": {"unknown_cost": True},
    }) == "UNKNOWN_COST"
    assert handoff_spend_block({
        "estimated_cost_eur": 0.0,
        "params": {"cost_class": "unknown"},
    }) == "UNKNOWN_COST"


@pytest.mark.parametrize("cost", [-1.0, float("nan"), float("inf"), True, "0"])
def test_invalid_cost_is_unknown(cost):
    assert handoff_spend_block({"estimated_cost_eur": cost}) == "UNKNOWN_COST"


def test_positive_cost_is_not_allowed():
    assert handoff_spend_block({"estimated_cost_eur": 99.0}) == "SPEND_NOT_ALLOWED_BY_POLICY"
    assert handoff_spend_block({"estimated_cost_eur": 1}) == "SPEND_NOT_ALLOWED_BY_POLICY"


def test_explicit_zero_is_allowed():
    assert handoff_spend_block({"estimated_cost_eur": 0.0}) is None
    assert handoff_spend_block({"estimated_cost_eur": 0}) is None
    assert handoff_spend_block({"params": {"estimated_cost_eur": 0.0}}) is None
    assert handoff_spend_block({
        "estimated_cost_eur": 0.0,
        "params": {"estimated_cost_eur": 0.0},
    }) is None


def test_disagreeing_estimates_are_unknown():
    assert handoff_spend_block({
        "estimated_cost_eur": 0.0,
        "params": {"estimated_cost_eur": 99.0},
    }) == "UNKNOWN_COST"
    assert handoff_spend_block({
        "estimated_cost_eur": 99.0,
        "params": {"estimated_cost_eur": 0.0},
    }) == "UNKNOWN_COST"


def test_local_shell_without_an_estimate_is_not_free():
    packet = {
        "adapter": "local_shell",
        "params": {"command": ["agy", "--print"], "write": "out.txt", "timeout_s": 30},
        "effect_class": "idempotent",
        "max_attempts": 1,
        "lease_ttl_s": 30,
    }
    assert "estimated_cost_eur" not in packet
    assert "estimated_cost_eur" not in packet["params"]
    assert handoff_spend_block(packet) == "UNKNOWN_COST"


def test_parked_view_does_not_invent_zero():
    body = spend_body_from_parked({
        "depends_on": [],
        "task": {"adapter": "local", "params": {"unit": "a"}},
    })
    assert "estimated_cost_eur" not in body
    assert handoff_spend_block(body) == "UNKNOWN_COST"


def test_parked_view_reads_task_zero_and_entry_zero():
    task = {"adapter": "local", "params": {"unit": "a"}, "estimated_cost_eur": 0.0}
    assert handoff_spend_block(spend_body_from_parked({"task": task})) is None
    entry = {"estimated_cost_eur": 0.0, "task": {"adapter": "local", "params": {}}}
    assert handoff_spend_block(spend_body_from_parked(entry)) is None


def test_parked_view_keeps_an_entry_mark_and_a_blocking_entry_amount():
    marked = {"unknown_cost": True, "task": {"estimated_cost_eur": 0.0, "params": {}}}
    assert handoff_spend_block(spend_body_from_parked(marked)) == "UNKNOWN_COST"
    hidden = {
        "estimated_cost_eur": 99.0,
        "task": {"estimated_cost_eur": 0.0, "params": {}},
    }
    assert handoff_spend_block(spend_body_from_parked(hidden)) == "SPEND_NOT_ALLOWED_BY_POLICY"
    kept = {
        "estimated_cost_eur": 0.0,
        "task": {"estimated_cost_eur": -1.0, "params": {}},
    }
    assert handoff_spend_block(spend_body_from_parked(kept)) == "UNKNOWN_COST"
