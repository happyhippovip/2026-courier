"""Catalog 2601-2625: uncolored setup time, closed support effort, delimited relay count.

Pure planning only. No network, no spend, no product-shell unlock.
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNNERS = (
    ROOT / "scripts" / "run_physical.py",
    ROOT / "scripts" / "run_physical_restart.py",
)


def _signal():
    from scripts.pilot_signal import (
        delimit_human_relay,
        plan_setup_time,
        record_support_effort,
        setup_budget_minutes,
    )

    return plan_setup_time, record_support_effort, delimit_human_relay, setup_budget_minutes


def test_published_setup_budgets_are_five_and_fifteen():
    _, _, _, setup_budget_minutes = _signal()
    budgets = setup_budget_minutes()
    assert budgets["gq46_minutes"] == 5
    assert budgets["dummy_minutes"] == 15
    assert budgets["agree"] is False


def test_setup_plan_stays_uncolored_on_both_sides_of_both_budgets():
    plan_setup_time, _, _, _ = _signal()
    for minutes in (0, 4.9, 5, 15, 15.1, 40):
        record = plan_setup_time(minutes, "fetch FINAL_SHA until worker polls")
        assert record["minutes"] == minutes
        assert record["method"] == "fetch FINAL_SHA until worker polls"
        assert record["verdict"] == "UNCOLORED"
        assert record["shell_unlocked"] is False
        assert "GREEN" not in record.values()
        assert "RED" not in record.values()


def test_setup_plan_rejects_bad_minutes_blank_method_and_caller_color():
    plan_setup_time, _, _, _ = _signal()
    with pytest.raises(ValueError):
        plan_setup_time(-1, "fetch FINAL_SHA until worker polls")
    with pytest.raises(ValueError):
        plan_setup_time(True, "fetch FINAL_SHA until worker polls")
    with pytest.raises(ValueError):
        plan_setup_time(3, "  ")
    with pytest.raises(ValueError):
        plan_setup_time(3, "fetch FINAL_SHA until worker polls", caller_verdict="GREEN")
    with pytest.raises(ValueError):
        plan_setup_time(3, "fetch FINAL_SHA until worker polls", caller_verdict="RED")


def test_setup_plan_is_the_same_on_a_second_call():
    plan_setup_time, _, _, _ = _signal()
    first = plan_setup_time(7, " wall clock ")
    second = plan_setup_time(7, " wall clock ")
    assert first == second
    assert first["method"] == "wall clock"


def test_support_effort_counts_out_of_band_prompts_only():
    _, record_support_effort, _, _ = _signal()
    zero = record_support_effort(0)
    assert zero == {
        "measure": "out_of_band_prompts",
        "count": 0,
        "meets_zero_target": True,
        "shell_unlocked": False,
    }
    some = record_support_effort(2)
    assert some["count"] == 2
    assert some["meets_zero_target"] is False
    assert some["shell_unlocked"] is False
    assert record_support_effort(2) == some


def test_support_effort_rejects_free_text_and_negative_counts():
    _, record_support_effort, _, _ = _signal()
    with pytest.raises(ValueError):
        record_support_effort("a lot of hand-holding")
    with pytest.raises(ValueError):
        record_support_effort(-1)
    with pytest.raises(ValueError):
        record_support_effort(True)
    with pytest.raises(ValueError):
        record_support_effort(1.5)


def test_literal_zero_is_not_a_human_relay_count():
    _, _, delimit_human_relay, _ = _signal()
    with pytest.raises(ValueError):
        delimit_human_relay(0, limit=0)


def test_unobserved_relay_has_no_numeric_count():
    _, _, delimit_human_relay, _ = _signal()
    record = delimit_human_relay(None, limit=0)
    assert record["status"] == "UNCOUNTED"
    assert "count" not in record
    assert record["limit"] == 0
    assert record["shell_unlocked"] is False
    assert delimit_human_relay(None, limit=0) == record


def test_counted_relays_stay_separate_from_the_limit():
    _, _, delimit_human_relay, _ = _signal()
    empty = delimit_human_relay([], limit=0)
    assert empty["status"] == "COUNTED"
    assert empty["count"] == 0
    assert empty["limit"] == 0
    assert empty["within_limit"] is True
    one = delimit_human_relay(["paste the API key"], limit=0)
    assert one["count"] == 1
    assert one["within_limit"] is False
    assert one["shell_unlocked"] is False


def test_physical_runners_do_not_publish_a_hardcoded_relay_zero():
    for path in RUNNERS:
        text = path.read_text(encoding="utf-8")
        assert '"human_relay_count": 0' not in text
        assert "human_relay_counter(" in text or "delimit_human_relay(None)" in text

