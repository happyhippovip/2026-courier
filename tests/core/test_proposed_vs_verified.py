"""Proposed is not verified (catalog 1976–1977).

Pins the existing task-machine and update-gate contracts. A worker result
that is only ready, and a human effect confirmation, must not be labeled
verified. Reloading the journal must not promote either of them.
"""

from courier_runtime.update_gate import CapabilityState, compare
from core_builders import Attempt, created, task_event
from courier_core.events import Event, EventType
from courier_core.journal import Journal
from courier_core.projection import fold, projection_hash, rebuild
from courier_core.state_machine import (
    RESOLVED_EFFECT_CONFIRMED,
    RESOLVED_VERIFIED,
    TaskState,
    TaskStatus,
    TransitionError,
    apply,
)

import pytest

INSTALLED = CapabilityState("1.0.0", {"LEDGER-01": True, "GOLDEN-01": True, "HUB-03": False}, "d1")


def _run(events, state=None):
    for event in events:
        state = apply(state, event)
    return state


def _ready(task_id="t-proposed"):
    attempt = Attempt(task_id)
    state = _run([created(task_id), attempt.claimed(), attempt.started(), attempt.result_ready()])
    return attempt, state


def _verified(task_id="t-verified"):
    attempt = Attempt(task_id)
    ready = _run([created(task_id), attempt.claimed(), attempt.started(), attempt.result_ready()])
    accepted = apply(ready, attempt.accepted())
    completed = apply(accepted, attempt.complete())
    return attempt, ready, accepted, completed


def _human_confirmed(task_id="t-human"):
    attempt = Attempt(task_id)
    lost = _run([
        created(task_id, effect_class="non_idempotent"),
        attempt.claimed(),
        attempt.started(),
        attempt.lease_expired(),
    ])
    blocked = apply(lost, task_event(EventType.TASK_BLOCKED, task_id=task_id, reason="uncertain"))
    confirmed = apply(blocked, Event(
        type=EventType.EFFECT_CONFIRMED,
        task_id=task_id,
        attempt=attempt.attempt,
        payload={"actor": "desk:ana", "reason": "saw the file"},
    ))
    return blocked, confirmed


def test_ready_result_cannot_be_completed_or_labeled_verified():
    attempt, ready = _ready()
    assert ready.status is TaskStatus.VERIFYING
    assert ready.resolution is None
    assert ready.pending_result_id == attempt.result_id
    assert ready.accepted_result_id is None
    with pytest.raises(TransitionError, match="accepted result"):
        apply(ready, attempt.complete())
    assert ready.resolution is None


def test_only_an_accepted_result_is_verified():
    _attempt, ready, accepted, completed = _verified()
    assert ready.resolution is None
    assert accepted.status is TaskStatus.ACCEPTED
    assert accepted.resolution == RESOLVED_VERIFIED
    assert completed.status is TaskStatus.COMPLETE
    assert completed.resolution == RESOLVED_VERIFIED


def test_human_effect_confirmation_is_not_verified():
    blocked, confirmed = _human_confirmed()
    assert blocked.resolution is None
    assert confirmed.status is TaskStatus.COMPLETE
    assert confirmed.resolution == RESOLVED_EFFECT_CONFIRMED
    assert confirmed.resolution != RESOLVED_VERIFIED
    assert confirmed.decided_by == "desk:ana"


def test_tampered_history_cannot_promote_a_proposed_capability():
    after = CapabilityState(
        "1.1.0",
        {"LEDGER-01": True, "GOLDEN-01": True, "HUB-03": True},
        "tampered",
    )
    result = compare(INSTALLED, after)
    assert result["decision"] == "REJECT"
    assert result["proposed"] == ["HUB-03"]
    assert "switch_to" not in result
    assert result["recovery"]["keep_version"] == INSTALLED.version
    joined = " ".join(result["reasons"])
    assert "HUB-03" not in joined
    assert "not yet accepted" not in joined


def test_resolution_roundtrip_does_not_promote_unverified_states():
    _attempt, ready = _ready("t-round-ready")
    _attempt, _ready_state, _accepted, verified = _verified("t-round-verified")
    _blocked, human = _human_confirmed("t-round-human")
    for state in (ready, verified, human):
        once = TaskState.from_record(state.to_record())
        twice = TaskState.from_record(once.to_record())
        assert twice == once == state
        if state is not verified:
            assert state.resolution != RESOLVED_VERIFIED


def test_compare_repeat_is_identical():
    after = CapabilityState("1.1.0", {"LEDGER-01": True, "GOLDEN-01": True, "HUB-03": True}, "d1")
    assert compare(INSTALLED, after) == compare(INSTALLED, after)


def test_journal_restart_keeps_proposed_and_verified_apart(tmp_path):
    proposed_events = [created("t-proposed"), *Attempt("t-proposed").happy()[:3]]
    verified_events = [created("t-verified"), *Attempt("t-verified").happy()]
    human_events = [
        created("t-human", effect_class="non_idempotent"),
        *Attempt("t-human").happy()[:2],
        Attempt("t-human").lease_expired(),
        task_event(EventType.TASK_BLOCKED, task_id="t-human", reason="uncertain"),
        Event(
            type=EventType.EFFECT_CONFIRMED,
            task_id="t-human",
            attempt=1,
            payload={"actor": "desk:ana", "reason": "saw the file"},
        ),
    ]
    # happy()[:2] is claimed+started; lease_expired follows. Matches _human_confirmed.
    path = tmp_path / "courier.db"
    events = proposed_events + verified_events + human_events
    with Journal(path) as journal:
        for event in events:
            journal.append(event)
        first_hash = projection_hash(journal.conn)
        assert journal.task("t-proposed").resolution is None
        assert journal.task("t-proposed").status is TaskStatus.VERIFYING
        assert journal.task("t-verified").resolution == RESOLVED_VERIFIED
        assert journal.task("t-human").resolution == RESOLVED_EFFECT_CONFIRMED

    with Journal(path) as reopened:
        assert projection_hash(reopened.conn) == first_hash
        assert reopened.task("t-proposed").resolution is None
        assert reopened.task("t-verified").resolution == RESOLVED_VERIFIED
        assert reopened.task("t-human").resolution == RESOLVED_EFFECT_CONFIRMED
        assert reopened.task("t-human").resolution != RESOLVED_VERIFIED
        for event in events:
            if event.dedupe_key is None:
                with pytest.raises(TransitionError, match="terminal"):
                    reopened.append(event)
            else:
                again = reopened.append(event)
                assert again.duplicate is True
        assert reopened.task("t-human").resolution == RESOLVED_EFFECT_CONFIRMED
        assert projection_hash(reopened.conn) == first_hash
        replayed = fold(reopened.events())
        assert replayed["t-proposed"].resolution is None
        assert replayed["t-verified"].resolution == RESOLVED_VERIFIED
        assert replayed["t-human"].resolution == RESOLVED_EFFECT_CONFIRMED
        rebuilt = rebuild(reopened, tmp_path / "rebuilt.db")

    with Journal(rebuilt, readonly=True) as replay:
        assert projection_hash(replay.conn) == first_hash
        assert replay.task("t-proposed").resolution is None
        assert replay.task("t-human").resolution == RESOLVED_EFFECT_CONFIRMED
