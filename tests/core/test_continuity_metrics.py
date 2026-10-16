"""Contract for human-relay count, restart success, and next-day return.

These metrics are missing on integration/v1. A hardcoded 0, agent prose, an
empty sample, or a tampered verified flag must not become a measured result.
"""

import json
from pathlib import Path

from courier_core.continuity_metrics import (
    MetricVerdict,
    count_human_relays,
    prepare_next_day_return,
    restart_success_rate,
)


SECRET = "sk-live-SUPERSECRETVALUE"


def test_module_does_not_read_clock_or_network():
    import courier_core.continuity_metrics as metrics

    source = Path(metrics.__file__).read_text(encoding="utf-8")
    assert "datetime.now" not in source
    assert "utcnow" not in source
    assert "urlopen" not in source
    assert "socket" not in source


def test_relay_counts_and_human_gate_does_not():
    verdict = count_human_relays([
        {"kind": "worker"},
        {"kind": "effect_confirmed", "actor": "human"},
        {"type": "RETRY_AUTHORIZED", "actor": "human"},
        {"kind": "cancel", "actor": "human"},
        {"kind": "human_relay", "actor": "human"},
        {"kind": "paste", "actor": "human", "text": "forwarded between A and B"},
        {"actor": "human", "role": "relay"},
    ])
    assert verdict.metric == "human_relays"
    assert verdict.status == "measured"
    assert verdict.count == 3
    assert verdict.verified is True
    assert verdict.reason == "measured"


def test_classified_workers_are_a_measured_zero():
    verdict = count_human_relays([{"kind": "worker"}, {"kind": "system"}])
    assert verdict.status == "measured"
    assert verdict.count == 0
    assert verdict.verified is True


def test_empty_event_list_is_not_a_measured_zero():
    verdict = count_human_relays([])
    assert verdict.status == "unmeasured"
    assert verdict.reason == "empty_sample"
    assert verdict.count is None
    assert verdict.verified is False


def test_explicit_complete_empty_journal_is_measured_zero():
    verdict = count_human_relays({"events": [], "sample_complete": True})
    assert verdict.status == "measured"
    assert verdict.count == 0
    assert verdict.verified is True


def test_hardcoded_zero_is_not_a_measurement():
    verdict = count_human_relays(0)
    assert verdict.status == "unmeasured"
    assert verdict.reason == "hardcoded_counter"
    assert verdict.count is None
    assert verdict.verified is False


def test_bool_is_not_a_sample():
    verdict = count_human_relays(False)
    assert verdict.status == "unmeasured"
    assert verdict.reason == "hardcoded_counter"
    assert verdict.count is None


def test_physical_snapshot_literal_zero_is_not_measured():
    snapshot = {
        "final_status": "SUCCESS",
        "execution_counters": {
            "process_a": 1,
            "process_b": 1,
            "human_relay_count": 0,
        },
    }
    verdict = count_human_relays(snapshot)
    assert verdict.status == "unmeasured"
    assert verdict.reason == "hardcoded_counter"
    assert verdict.count is None
    assert verdict.verified is False


def test_agent_prose_is_not_a_receipt():
    verdict = count_human_relays("HUMAN_RELAY_COUNT=0")
    assert verdict.status == "unmeasured"
    assert verdict.reason == "prose_not_receipt"
    assert verdict.count is None
    assert verdict.verified is False
    assert "HUMAN_RELAY_COUNT=0" not in verdict.to_json()


def test_prose_event_does_not_zero_a_relay():
    verdict = count_human_relays([
        {"kind": "human_relay", "actor": "human"},
        {"kind": "prose", "text": "HUMAN_RELAY_COUNT=0"},
    ])
    assert verdict.status == "unmeasured"
    assert verdict.reason == "prose_not_receipt"
    assert verdict.count is None
    assert verdict.verified is False


def test_unknown_kind_fails_closed():
    verdict = count_human_relays([{"kind": "worker"}, {"kind": "mystery"}])
    assert verdict.status == "unmeasured"
    assert verdict.reason == "unknown_event"
    assert verdict.count is None
    assert verdict.verified is False


def test_conflicting_role_and_kind_fails_closed():
    verdict = count_human_relays([
        {"kind": "effect_confirmed", "role": "relay", "actor": "human"},
    ])
    assert verdict.status == "unmeasured"
    assert verdict.reason == "unknown_event"
    assert verdict.count is None


def test_secret_text_stays_out_of_the_verdict():
    verdict = count_human_relays([
        {"kind": "human_relay", "actor": "human", "text": SECRET},
    ])
    assert verdict.count == 1
    assert SECRET not in verdict.to_json()
    assert SECRET not in verdict.reason


def test_reload_is_idempotent():
    verdict = count_human_relays([{"kind": "worker"}, {"kind": "human_gate", "actor": "human"}])
    again = MetricVerdict.from_json(verdict.to_json())
    assert again == verdict
    assert MetricVerdict.from_json(again.to_json()) == again


def test_tampered_count_fails_closed():
    verdict = count_human_relays([{"kind": "human_relay", "actor": "human"}])
    raw = json.loads(verdict.to_json())
    raw["count"] = 0
    raw["verified"] = True
    again = MetricVerdict.from_json(json.dumps(raw))
    assert again.status == "rejected"
    assert again.verified is False
    assert again.count is None
    assert again.reason == "tampered"


def test_tampered_verified_flag_on_unmeasured_fails_closed():
    verdict = count_human_relays(0)
    raw = json.loads(verdict.to_json())
    assert raw["verified"] is False
    raw["verified"] = True
    again = MetricVerdict.from_json(json.dumps(raw))
    assert again.status == "rejected"
    assert again.verified is False
    assert again.reason == "tampered"


def test_derived_verified_follows_an_intact_body():
    verdict = count_human_relays([{"kind": "system"}])
    raw = json.loads(verdict.to_json())
    raw["verified"] = False
    again = MetricVerdict.from_json(json.dumps(raw))
    assert again.status == "measured"
    assert again.count == 0
    assert again.verified is True


def test_verdict_status_is_not_a_catalog_verified_claim():
    verdict = count_human_relays([{"kind": "worker"}])
    assert verdict.status in {"measured", "unmeasured", "rejected"}
    assert "REAL_EXECUTION_PROVEN" not in verdict.to_json()


def test_empty_restart_sample_is_not_one_hundred_percent():
    verdict = restart_success_rate([])
    assert verdict.metric == "restart_success"
    assert verdict.status == "unmeasured"
    assert verdict.reason == "empty_sample"
    assert verdict.successes is None
    assert verdict.measured is None
    assert verdict.verified is False


def test_complete_empty_restart_sample_is_still_not_a_rate():
    verdict = restart_success_rate({"attempts": [], "sample_complete": True})
    assert verdict.status == "unmeasured"
    assert verdict.reason == "empty_sample"
    assert verdict.successes is None


def test_restart_success_is_resume_without_replay():
    verdict = restart_success_rate([
        {"attempt_id": "a", "outcome": "resumed_without_replay"},
        {"attempt_id": "b", "outcome": "replayed"},
        {"attempt_id": "c", "outcome": "failed"},
        {"attempt_id": "d", "outcome": "uncertain"},
    ])
    assert verdict.status == "measured"
    assert verdict.successes == 1
    assert verdict.measured == 4
    assert verdict.verified is True
    blob = verdict.to_json()
    assert "0.25" not in blob
    assert "1.0" not in blob


def test_missing_restart_outcome_fails_closed():
    verdict = restart_success_rate([
        {"attempt_id": "a", "outcome": "resumed_without_replay"},
        {"attempt_id": "b"},
    ])
    assert verdict.status == "unmeasured"
    assert verdict.reason == "missing_outcome"
    assert verdict.successes is None
    assert verdict.verified is False


def test_duplicate_restart_attempt_is_not_two_successes():
    verdict = restart_success_rate([
        {"attempt_id": "a", "outcome": "resumed_without_replay"},
        {"attempt_id": "a", "outcome": "resumed_without_replay"},
    ])
    assert verdict.status == "unmeasured"
    assert verdict.reason == "duplicate_attempt"
    assert verdict.successes is None


def test_restart_prose_is_not_a_receipt():
    verdict = restart_success_rate("restart success rate is 100%")
    assert verdict.status == "unmeasured"
    assert verdict.reason == "prose_not_receipt"
    assert verdict.successes is None
    assert "100%" not in verdict.to_json()


def test_restart_reload_is_idempotent():
    verdict = restart_success_rate([
        {"outcome": "resumed_without_replay"},
        {"outcome": "uncertain"},
    ])
    assert MetricVerdict.from_json(verdict.to_json()) == verdict


def test_restart_rate_tamper_fails_closed():
    verdict = restart_success_rate([{"outcome": "replayed"}])
    raw = json.loads(verdict.to_json())
    raw["successes"] = 1
    raw["verified"] = True
    again = MetricVerdict.from_json(json.dumps(raw))
    assert again.status == "rejected"
    assert again.verified is False
    assert again.successes is None


def test_plan_without_a_later_observation_is_not_a_rate():
    verdict = prepare_next_day_return({
        "prior_day_id": "day-1",
        "prior_date": "2026-10-12",
    })
    assert verdict.metric == "next_day_return"
    assert verdict.status == "unmeasured"
    assert verdict.reason == "not_yet"
    assert verdict.successes is None
    assert verdict.measured is None
    assert verdict.verified is False


def test_same_calendar_day_is_not_a_next_day_return():
    verdict = prepare_next_day_return({
        "prior_day_id": "day-1",
        "prior_date": "2026-10-12",
        "subjects": [{
            "subject_id": "a",
            "observation_date": "2026-10-12",
            "checked": True,
            "returned": True,
        }],
    })
    assert verdict.status == "unmeasured"
    assert verdict.reason == "same_calendar_day"
    assert verdict.successes is None


def test_earlier_observation_is_not_a_return():
    verdict = prepare_next_day_return({
        "prior_day_id": "day-1",
        "prior_date": "2026-10-12",
        "subjects": [{
            "subject_id": "a",
            "observation_date": "2026-10-11",
            "checked": True,
            "returned": True,
        }],
    })
    assert verdict.status == "unmeasured"
    assert verdict.reason == "not_later_day"
    assert verdict.successes is None


def test_checked_later_days_are_a_count_pair():
    verdict = prepare_next_day_return({
        "prior_day_id": "day-1",
        "prior_date": "2026-10-12",
        "subjects": [
            {
                "subject_id": "a",
                "observation_date": "2026-10-13",
                "checked": True,
                "returned": True,
            },
            {
                "subject_id": "b",
                "observation_date": "2026-10-14",
                "checked": True,
                "returned": False,
            },
        ],
    })
    assert verdict.status == "measured"
    assert verdict.successes == 1
    assert verdict.measured == 2
    assert verdict.verified is True
    assert "0.5" not in verdict.to_json()


def test_unchecked_subject_is_not_a_zero_return():
    verdict = prepare_next_day_return({
        "prior_day_id": "day-1",
        "prior_date": "2026-10-12",
        "subjects": [{
            "subject_id": "a",
            "observation_date": "2026-10-13",
            "checked": False,
            "returned": False,
        }],
    })
    assert verdict.status == "unmeasured"
    assert verdict.reason == "not_yet"
    assert verdict.successes is None


def test_prose_return_signal_is_not_a_measurement():
    verdict = prepare_next_day_return({
        "prior_day_id": "day-1",
        "prior_date": "2026-10-12",
        "subjects": [{
            "subject_id": "a",
            "observation_date": "2026-10-13",
            "checked": True,
            "returned": "the user came back",
        }],
    })
    assert verdict.status == "unmeasured"
    assert verdict.reason == "prose_signal"
    assert verdict.successes is None


def test_next_day_prose_claim_is_not_a_receipt():
    verdict = prepare_next_day_return("NDR is 100% voluntary return")
    assert verdict.status == "unmeasured"
    assert verdict.reason == "prose_not_receipt"
    assert "100%" not in verdict.to_json()


def test_duplicate_subject_fails_closed():
    verdict = prepare_next_day_return({
        "prior_day_id": "day-1",
        "prior_date": "2026-10-12",
        "subjects": [
            {
                "subject_id": "a",
                "observation_date": "2026-10-13",
                "checked": True,
                "returned": True,
            },
            {
                "subject_id": "a",
                "observation_date": "2026-10-13",
                "checked": True,
                "returned": True,
            },
        ],
    })
    assert verdict.status == "unmeasured"
    assert verdict.reason == "duplicate_subject"
    assert verdict.successes is None


def test_next_day_secret_stays_out_of_the_verdict():
    verdict = prepare_next_day_return({
        "prior_day_id": "day-1",
        "prior_date": "2026-10-12",
        "subjects": [{
            "subject_id": SECRET,
            "observation_date": "2026-10-13",
            "checked": True,
            "returned": True,
            "note": SECRET,
        }],
    })
    assert verdict.status == "measured"
    assert verdict.successes == 1
    assert SECRET not in verdict.to_json()


def test_next_day_reload_and_tamper():
    verdict = prepare_next_day_return({
        "prior_day_id": "day-1",
        "prior_date": "2026-10-12",
        "subjects": [{
            "subject_id": "a",
            "observation_date": "2026-10-13",
            "checked": True,
            "returned": True,
        }],
    })
    assert MetricVerdict.from_json(verdict.to_json()) == verdict
    raw = json.loads(verdict.to_json())
    raw["successes"] = 0
    raw["verified"] = True
    again = MetricVerdict.from_json(json.dumps(raw))
    assert again.status == "rejected"
    assert again.verified is False
    assert again.successes is None
