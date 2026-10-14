"""create_task refuses a missing or ambiguous goal before anything can be claimed."""

import pytest

from ctrl_helpers import make_controller, task_body
from courier_core.controller import ApiError
from courier_core.goal_contract import draft_goal_contract


def _goal(**overrides):
    goal = {
        "goal_id": "goal-dispatch",
        "end_result": "out.txt exists and its sha256 matches the fixture",
        "allowed_scope": ["out.txt"],
        "forbidden_scope": ["secrets"],
        "constraints": ["no network"],
        "acceptance_criteria": [
            {"id": "artifact", "check": "sha256 matches the fixture", "evidence_class": "deterministic"},
        ],
        "side_effect_limits": ["no commits"],
        "gates": {"human": True, "money": False, "safety": True},
    }
    goal.update(overrides)
    return goal


@pytest.fixture
def ctl(tmp_path):
    controller = make_controller(tmp_path / "home")
    yield controller
    controller.stop()


def api_error(fn, *args):
    with pytest.raises(ApiError) as info:
        fn(*args)
    return info.value


def _journal_types(ctl):
    return [event.type.value for event in ctl.journal.events()]


def test_missing_goal_is_not_dispatched(ctl):
    for goal in (None, {}, "", {"goal_id": "goal-dispatch"}):
        err = api_error(ctl.create_task, task_body(goal=goal))
        assert err.status == 409 and err.code == "needs_clarification"
        assert err.extra["outcome"] == "NEEDS_CLARIFICATION"
        assert "missing_goal" in err.extra["reasons"]
    assert _journal_types(ctl) == ["CONTROLLER_STARTED"]
    assert ctl.claim({"worker_id": "w1"}) is None


def test_ambiguous_goal_needs_clarification_and_is_not_dispatched(ctl):
    err = api_error(ctl.create_task, task_body(goal=_goal(end_result="fix the bug or maybe rewrite the module")))
    assert err.status == 409 and err.code == "needs_clarification"
    assert err.extra["outcome"] == "NEEDS_CLARIFICATION"
    assert err.extra["reasons"] == ["ambiguous_goal"]
    assert _journal_types(ctl) == ["CONTROLLER_STARTED"]
    assert ctl.claim({"worker_id": "w1"}) is None


def test_clear_goal_is_drafted_and_dispatched(ctl):
    goal = _goal()
    status, body = ctl.create_task(task_body(goal=goal))
    assert status == 201
    created = next(event for event in ctl.journal.events(task_id=body["task_id"])
                   if event.type.value == "TASK_CREATED")
    draft = draft_goal_contract(goal)
    assert draft.contract is not None
    assert created.payload["goal_id"] == "goal-dispatch"
    assert created.payload["goal_fingerprint"] == draft.contract.fingerprint()
    lease = ctl.claim({"worker_id": "w1"})
    assert lease is not None and lease["task_id"] == body["task_id"]
    assert ctl.claim({"worker_id": "w2"}) is None
