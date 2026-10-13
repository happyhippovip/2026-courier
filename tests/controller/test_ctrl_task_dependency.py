"""L2 controller: a task with depends_on runs only on the verified result of that task."""

import hashlib

import pytest

from ctrl_helpers import FakeClock, SHA, Verifiers, accept_all, make_controller, result_body, sha_matches, task_body, types
from courier_core.controller import ApiError
from courier_core.events import Event, EventType, EventValidationError
from courier_core.state_machine import TaskStatus, TransitionError

OTHER_SHA = hashlib.sha256(b"something else").hexdigest()


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def ctl(tmp_path, clock):
    controller = make_controller(tmp_path / "home", clock=clock)
    yield controller
    controller.stop()


def create(ctl, **overrides):
    return ctl.create_task(task_body(**overrides))[1]["task_id"]


def pair(ctl, **b_overrides):
    a = create(ctl)
    return a, create(ctl, depends_on=a, **b_overrides)


def finish(ctl, lease, result_id="r1", sha=SHA):
    """start -> result -> verify for a claimed lease."""
    ctl.start({"dispatch_id": lease["dispatch_id"]})
    ctl.result(result_body(lease["dispatch_id"], result_id=result_id, sha=sha))
    ctl.drain()


def claim(ctl, worker="w1"):
    return ctl.claim({"worker_id": worker})


def status(ctl, task_id):
    return ctl.journal.task(task_id).status


def pass_time(ctl, clock, seconds, step=0.25):
    elapsed = 0.0
    while elapsed < seconds:
        delta = min(step, seconds - elapsed)
        clock.advance(delta)
        elapsed += delta
        ctl.tick()


def expected_input(a, lease_a, result_id="r1", sha=SHA):
    return {"task_id": a, "dispatch_id": lease_a["dispatch_id"], "result_id": result_id,
            "artifacts": [{"path": "out.txt", "sha256": sha}]}


# ------------------------------------------------------------ waiting and binding
def test_dependent_task_is_not_claimable_before_its_dependency_is_verified(ctl):
    a, b = pair(ctl)
    lease_a = claim(ctl)
    assert lease_a["task_id"] == a
    assert claim(ctl) is None  # A is CLAIMED
    ctl.start({"dispatch_id": lease_a["dispatch_id"]})
    assert claim(ctl) is None  # A is RUNNING
    ctl.result(result_body(lease_a["dispatch_id"]))
    assert status(ctl, a) is TaskStatus.VERIFYING
    assert claim(ctl) is None  # A is VERIFYING
    assert status(ctl, b) is TaskStatus.QUEUED
    assert types(ctl, b) == ["TASK_CREATED"]


def test_dependent_task_is_claimed_with_the_verified_result_as_input(ctl):
    a, b = pair(ctl)
    lease_a = claim(ctl)
    finish(ctl, lease_a)
    assert status(ctl, a) is TaskStatus.COMPLETE

    lease_b = claim(ctl)
    assert lease_b["task_id"] == b
    want = expected_input(a, lease_a)
    assert lease_b["spec"]["input"] == want
    claimed = [e for e in ctl.journal.events(task_id=b) if e.type is EventType.TASK_CLAIMED]
    assert len(claimed) == 1 and claimed[0].payload == {"ttl_s": 6, "input": want}
    view = ctl.task_view(b)
    assert (view["depends_on"], view["input"]) == (a, want)
    assert ctl.journal.task(b).input == want  # what a verifier is handed as task.input

    finish(ctl, lease_b)
    assert status(ctl, b) is TaskStatus.COMPLETE
    assert claim(ctl) is None  # nothing is handed out twice


def test_input_carries_the_hash_of_the_result_that_was_actually_accepted(tmp_path, clock):
    ctl = make_controller(tmp_path / "home", clock=clock, verifier=Verifiers(probe=accept_all))
    try:
        a, b = pair(ctl)
        lease_a = claim(ctl)
        finish(ctl, lease_a, result_id="r-real", sha=OTHER_SHA)
        assert claim(ctl)["spec"]["input"] == expected_input(a, lease_a, result_id="r-real", sha=OTHER_SHA)
    finally:
        ctl.stop()


def test_a_chain_runs_in_order_each_on_the_previous_result(ctl):
    a = create(ctl)
    b = create(ctl, depends_on=a)
    c = create(ctl, depends_on=b)
    lease_a = claim(ctl)
    finish(ctl, lease_a)
    lease_b = claim(ctl)
    assert lease_b["task_id"] == b and claim(ctl) is None  # C waits for B
    finish(ctl, lease_b, result_id="r2")
    lease_c = claim(ctl)
    assert lease_c["task_id"] == c
    assert lease_c["spec"]["input"] == expected_input(b, lease_b, result_id="r2")


def test_independent_tasks_are_unchanged(ctl):
    a = create(ctl)
    lease = claim(ctl)
    assert "input" not in lease["spec"]
    claimed = [e for e in ctl.journal.events(task_id=a) if e.type is EventType.TASK_CLAIMED][0]
    assert claimed.payload == {"ttl_s": 6}
    view = ctl.task_view(a)
    assert (view["depends_on"], view["input"]) == (None, None)


def test_a_retried_dependent_task_gets_the_same_input_again(tmp_path, clock):
    verdicts = iter([True, False, True])  # A accepted, B attempt 1 rejected (retryable), B attempt 2 accepted

    def verify(task, result, home):
        from courier_core.verification import Verdict
        return Verdict(True, "ok") if next(verdicts) else Verdict(False, "try again", retryable=True)

    ctl = make_controller(tmp_path / "home", clock=clock, verifier=Verifiers(probe=verify))
    try:
        a, b = pair(ctl)
        lease_a = claim(ctl)
        finish(ctl, lease_a)
        first = claim(ctl)
        finish(ctl, first, result_id="b1")
        assert status(ctl, b) is TaskStatus.QUEUED
        second = claim(ctl)
        assert second["attempt"] == 2 and second["dispatch_id"] != first["dispatch_id"]
        assert second["spec"]["input"] == first["spec"]["input"] == expected_input(a, lease_a)
    finally:
        ctl.stop()


# ------------------------------------------------- a dependency without a verified result
def test_dependent_task_fails_when_its_dependency_is_rejected(tmp_path, clock):
    ctl = make_controller(tmp_path / "home", clock=clock, verifier=Verifiers(probe=sha_matches))
    try:
        a, b = pair(ctl)
        finish(ctl, claim(ctl), sha=OTHER_SHA)  # rejected, not retryable
        assert status(ctl, a) is TaskStatus.FAILED
        assert claim(ctl) is None
        assert status(ctl, b) is TaskStatus.FAILED
        assert types(ctl, b) == ["TASK_CREATED", "TASK_FAILED"]  # never claimed, never started
        assert a in ctl.journal.task(b).last_reason and "FAILED" in ctl.journal.task(b).last_reason
    finally:
        ctl.stop()


def test_dependent_task_fails_when_its_dependency_is_cancelled(ctl):
    a, b = pair(ctl)
    ctl.cancel(a)
    assert status(ctl, a) is TaskStatus.CANCELLED
    assert claim(ctl) is None
    assert status(ctl, b) is TaskStatus.FAILED


def test_blocked_dependency_keeps_the_dependent_task_waiting_and_a_human_confirmation_is_not_a_result(ctl, clock):
    a = create(ctl, effect_class="non_idempotent")
    b = create(ctl, depends_on=a)
    lease_a = claim(ctl)
    ctl.start({"dispatch_id": lease_a["dispatch_id"]})
    pass_time(ctl, clock, 7)  # the lease is lost after the attempt started: outcome unknown
    assert status(ctl, a) is TaskStatus.BLOCKED
    assert claim(ctl) is None
    assert status(ctl, b) is TaskStatus.QUEUED  # a human may still authorize a retry of A

    ctl.resolve(a, {"decision": "effect_confirmed", "actor": "ops", "attempt": 1, "reason": "seen at the provider"})
    assert status(ctl, a) is TaskStatus.COMPLETE
    assert claim(ctl) is None
    assert status(ctl, b) is TaskStatus.FAILED  # no verified artifact exists to build on
    assert "without a verified result" in ctl.journal.task(b).last_reason


# ------------------------------------------------------------------------ restart
def test_restart_after_the_dependency_completed_dispatches_the_dependent_task_exactly_once(tmp_path, clock):
    home = tmp_path / "home"
    ctl = make_controller(home, clock=clock)
    a, b = pair(ctl)
    lease_a = claim(ctl)
    finish(ctl, lease_a)
    ctl.stop()

    ctl = make_controller(home, clock=clock)
    try:
        assert status(ctl, a) is TaskStatus.COMPLETE
        lease_b = claim(ctl)
        assert lease_b["task_id"] == b and lease_b["attempt"] == 1
        assert lease_b["spec"]["input"] == expected_input(a, lease_a)
        assert claim(ctl) is None
    finally:
        ctl.stop()

    ctl = make_controller(home, clock=clock)  # restart while B is claimed
    try:
        assert status(ctl, b) is TaskStatus.CLAIMED
        assert claim(ctl) is None  # neither A again nor a second dispatch of B
        assert [t for t in types(ctl, a)].count("TASK_CLAIMED") == 1
        assert [t for t in types(ctl, b)].count("TASK_CLAIMED") == 1
        assert ctl.journal.verify_chain().ok and ctl.journal.verify_projection()
        assert ctl.task_view(b)["input"] == expected_input(a, lease_a)
    finally:
        ctl.stop()


# ---------------------------------------------------------------------- intake
def test_create_task_refuses_an_unknown_or_malformed_dependency(ctl):
    with pytest.raises(ApiError) as info:
        ctl.create_task(task_body(depends_on="task-does-not-exist"))
    assert (info.value.status, info.value.code) == (400, "unknown_dependency")
    with pytest.raises(ApiError) as info:
        ctl.create_task(task_body(depends_on=7))
    assert (info.value.status, info.value.code) == (400, "invalid_request")
    assert ctl.journal.tasks() == []


def test_a_task_cannot_depend_on_itself():
    with pytest.raises(EventValidationError):
        Event(type=EventType.TASK_CREATED, task_id="t1", payload={
            "adapter": "probe", "params": {}, "effect_class": "idempotent", "max_attempts": 1, "lease_ttl_s": 6,
            "depends_on": "t1"})


# ------------------------------------------------------------ the ledger's own rules
def claim_event(task_id, **payload):
    return Event(type=EventType.TASK_CLAIMED, task_id=task_id, attempt=1, dispatch_id="dsp-x", worker_id="w1",
                 payload={"ttl_s": 6, **payload})


def test_the_journal_refuses_a_dependent_claim_without_the_right_input(ctl):
    a, b = pair(ctl)
    other = create(ctl)
    good = {"task_id": a, "dispatch_id": "dsp-a", "result_id": "r1", "artifacts": [{"path": "out.txt", "sha256": SHA}]}
    with pytest.raises(TransitionError):
        ctl.journal.append(claim_event(b))
    with pytest.raises(TransitionError):
        ctl.journal.append(claim_event(b, input={**good, "task_id": other}))
    with pytest.raises(TransitionError):
        ctl.journal.append(claim_event(other, input=good))  # an independent task takes no input
    assert status(ctl, b) is TaskStatus.QUEUED and status(ctl, other) is TaskStatus.QUEUED


@pytest.mark.parametrize("bad", [
    {"task_id": "a", "dispatch_id": "d", "result_id": "r"},  # no artifacts
    {"task_id": "a", "dispatch_id": "d", "result_id": "r", "artifacts": []},  # nothing to build on
    {"task_id": "a", "dispatch_id": "d", "result_id": "r", "artifacts": [{"path": "out.txt", "sha256": "nope"}]},
    {"task_id": "a", "dispatch_id": "d", "result_id": "r", "artifacts": [{"path": "o", "sha256": SHA}], "extra": 1},
    {"task_id": "", "dispatch_id": "d", "result_id": "r", "artifacts": [{"path": "o", "sha256": SHA}]},
    "not-an-object",
])
def test_a_malformed_input_never_becomes_an_event(bad):
    with pytest.raises(EventValidationError):
        claim_event("b", input=bad)
