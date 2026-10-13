"""The motor must not treat the producer as the independent reviewer."""
import json

from scripts import courier_motor_precheck as motor
from scripts.courier_motor_precheck import has_dispatchable_work


def independent_review_ok(step):
    return motor.independent_review_ok(step)


def record_independent_review(step, review):
    return motor.record_independent_review(step, review)


def _state(step):
    return {
        "goals": {
            "g1": {
                "status": "ACTIVE",
                "current_step_index": 0,
                "workflow_plan": [step],
            }
        }
    }


def _step(**extra):
    step = {
        "status": "QUEUED",
        "target_agent": "github",
        "author_id": "producer-a",
        "requires_independent_review": True,
    }
    step.update(extra)
    return step


def _accept(**extra):
    review = {
        "event_id": "rev-1",
        "reviewer_id": "reviewer-b",
        "author_id": "producer-a",
        "source": "LEDGER_RECEIPT",
        "evidence_ref": "receipts/rev-1.json",
        "verdict": "ACCEPT",
    }
    review.update(extra)
    return review


def test_required_review_without_a_reviewer_is_not_work():
    assert has_dispatchable_work(_state(_step())) is False


def test_same_actor_self_report_and_reject_do_not_open_the_gate():
    same = _step(independent_review=_accept(reviewer_id="producer-a"))
    story = _step(independent_review=_accept(source="SELF_REPORT"))
    rejected = _step(independent_review=_accept(verdict="REJECT"))
    missing = _step(independent_review=_accept(evidence_ref=""))
    assert independent_review_ok(same) is False
    assert independent_review_ok(story) is False
    assert independent_review_ok(rejected) is False
    assert independent_review_ok(missing) is False
    assert has_dispatchable_work(_state(same)) is False
    assert has_dispatchable_work(_state(story)) is False


def test_distinct_reviewer_allows_the_queued_github_step():
    step = _step(independent_review=_accept())
    assert independent_review_ok(step) is True
    assert has_dispatchable_work(_state(step)) is True


def test_review_record_survives_reload_and_does_not_replay():
    step = _step()
    review = _accept()
    assert record_independent_review(step, review) is True
    assert record_independent_review(step, dict(review)) is False
    assert len(step["independent_reviews"]) == 1
    restored = json.loads(json.dumps(_state(step)))
    assert has_dispatchable_work(restored) is True
    again = restored["goals"]["g1"]["workflow_plan"][0]
    assert record_independent_review(again, review) is False
    assert len(again["independent_reviews"]) == 1


def test_unmarked_step_keeps_the_existing_dispatch_rule():
    assert has_dispatchable_work(_state({
        "status": "QUEUED",
        "target_agent": "github-actions",
    })) is True
