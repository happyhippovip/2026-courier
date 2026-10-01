"""L2 controller: tasks, claim, start, heartbeat, leases, results, verification, cancel (in-process)."""

import pytest

from ctrl_helpers import (
    FakeClock, Verifiers, make_controller, result_body, run_attempt, sha_matches, task_body, types,
)
from courier_core.controller import ApiError, heartbeat_interval
from courier_core.projection import projection_hash
from courier_core.state_machine import TaskStatus
from courier_core.verification import Verdict

GOLDEN = ["TASK_CREATED", "TASK_CLAIMED", "TASK_STARTED", "RESULT_READY", "RESULT_ACCEPTED", "TASK_COMPLETE"]


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def ctl(tmp_path, clock):
    controller = make_controller(tmp_path / "home", clock=clock)
    yield controller
    controller.stop()


def pass_time(ctl, clock, seconds, step=0.25):
    """Advance time the way the real ticker sees it: in small steps."""
    elapsed = 0.0
    while elapsed < seconds:
        delta = min(step, seconds - elapsed)
        clock.advance(delta)
        elapsed += delta
        ctl.tick()


def api_error(fn, *args):
    with pytest.raises(ApiError) as info:
        fn(*args)
    return info.value


# ---------------------------------------------------------------- C. tasks
def test_golden_sequence_through_controller(ctl):
    status, body = ctl.create_task(task_body())
    assert status == 201
    run_attempt(ctl)
    ctl.drain()
    assert types(ctl, body["task_id"]) == GOLDEN
    assert ctl.journal.task(body["task_id"]).status is TaskStatus.COMPLETE


@pytest.mark.parametrize("bad, field", [
    ({"unknown": 1}, "unknown field"),
    ({"adapter": "../evil"}, "adapter"),
    ({"adapter": ""}, "adapter"),
    ({"params": []}, "params"),
    ({"effect_class": "maybe"}, "effect_class"),
    ({"max_attempts": 0}, "max_attempts"),
    ({"max_attempts": True}, "max_attempts"),
    ({"lease_ttl_s": 0}, "lease_ttl_s"),
    ({"lease_ttl_s": 3601}, "lease_ttl_s"),
    ({"timeout_s": -1}, "timeout_s"),
    ({"timeout_s": "5"}, "timeout_s"),
])
def test_task_input_is_validated_strictly(ctl, bad, field):
    err = api_error(ctl.create_task, task_body(**bad))
    assert err.status == 400 and field in err.message
    assert ctl.journal.tasks() == []


def test_non_object_body_is_rejected(ctl):
    assert api_error(ctl.create_task, ["x"]).status == 400


def test_idempotency_key_makes_creation_repeatable(ctl):
    first = ctl.create_task(task_body(idempotency_key="order-42"))
    again = ctl.create_task(task_body(idempotency_key="order-42"))
    assert first[0] == 201 and again[0] == 200 and again[1]["duplicate"]
    assert first[1]["task_id"] == again[1]["task_id"]
    assert api_error(ctl.create_task, task_body(idempotency_key="order-42", max_attempts=1)).status == 409
    assert len(ctl.journal.tasks()) == 1


def test_task_creation_writes_only_the_journal(ctl):
    ctl.create_task(task_body(timeout_s=30))
    files = sorted(p.name for p in ctl.home.iterdir())
    assert all(name.startswith("courier.db") for name in files), files


# ---------------------------------------------------------------- D. claim
def test_claim_returns_lease_and_spec(ctl):
    _, body = ctl.create_task(task_body(timeout_s=30))
    lease = ctl.claim({"worker_id": "w1"})
    assert lease["task_id"] == body["task_id"] and lease["attempt"] == 1
    assert lease["dispatch_id"].startswith("dsp-") and lease["ttl_s"] == 6
    assert lease["heartbeat_s"] == heartbeat_interval(6) <= 6 / 3
    assert lease["spec"] == {"adapter": "probe", "params": {"x": 1}, "effect_class": "idempotent", "timeout_s": 30}
    assert ctl.claim({"worker_id": "w2"}) is None


def test_claim_order_is_creation_order(ctl):
    ids = [ctl.create_task(task_body())[1]["task_id"] for _ in range(3)]
    assert [ctl.claim({"worker_id": "w"})["task_id"] for _ in range(3)] == ids


def test_claim_validates_worker_id(ctl):
    assert api_error(ctl.claim, {}).status == 400
    assert api_error(ctl.claim, {"worker_id": "w", "extra": 1}).status == 400


# ---------------------------------------------------------------- E. start
def test_start_is_bound_to_the_exact_dispatch(ctl):
    ctl.create_task(task_body())
    lease = ctl.claim({"worker_id": "w1"})
    assert api_error(ctl.start, {"dispatch_id": "dsp-unknown"}).status == 404
    assert api_error(ctl.start, {"dispatch_id": lease["dispatch_id"], "worker_id": "intruder"}).status == 409
    assert ctl.start({"dispatch_id": lease["dispatch_id"]})["status"] == "STARTED"
    assert ctl.start({"dispatch_id": lease["dispatch_id"]})["status"] == "ALREADY_STARTED"
    assert types(ctl, lease["task_id"]).count("TASK_STARTED") == 1


def test_start_of_an_expired_dispatch_is_stale(ctl, clock):
    ctl.create_task(task_body())
    lease = ctl.claim({"worker_id": "w1"})
    pass_time(ctl, clock, 7)
    err = api_error(ctl.start, {"dispatch_id": lease["dispatch_id"]})
    assert err.status == 409 and err.code == "stale_dispatch"


# ------------------------------------------------- F. heartbeat and G. expiry
def test_heartbeats_keep_the_lease_alive(ctl, clock):
    _, body = ctl.create_task(task_body())
    lease = ctl.claim({"worker_id": "w1"})
    ctl.start({"dispatch_id": lease["dispatch_id"]})
    for _ in range(10):
        clock.advance(2)
        assert ctl.heartbeat({"worker_id": "w1", "dispatch_ids": [lease["dispatch_id"]]})["stop"] == []
        ctl.tick()
    assert "LEASE_EXPIRED" not in types(ctl, body["task_id"])


def test_heartbeat_from_wrong_worker_or_for_unknown_dispatch_says_stop(ctl, clock):
    ctl.create_task(task_body())
    lease = ctl.claim({"worker_id": "w1"})
    answer = ctl.heartbeat({"worker_id": "w2", "dispatch_ids": [lease["dispatch_id"], "dsp-ghost"]})
    assert answer["stop"] == sorted([lease["dispatch_id"], "dsp-ghost"])
    pass_time(ctl, clock, 6.1)  # w2's heartbeat did not refresh w1's lease
    assert ctl.journal.task(lease["task_id"]).status is TaskStatus.QUEUED


def test_heartbeat_input_is_bounded(ctl):
    assert api_error(ctl.heartbeat, {"worker_id": "w", "dispatch_ids": "x"}).status == 400
    assert api_error(ctl.heartbeat, {"worker_id": "w", "dispatch_ids": ["d"] * 257}).status == 400


def test_lease_deadline_is_never_stored(ctl):
    ctl.create_task(task_body())
    ctl.claim({"worker_id": "w1"})
    columns = {row[1] for row in ctl.journal.conn.execute("PRAGMA table_info(tasks)")}
    assert not {c for c in columns if "deadline" in c or "expires" in c or c.endswith("_at")}
    claim = next(e for e in ctl.journal.events() if e.type.value == "TASK_CLAIMED")
    assert claim.payload == {"ttl_s": 6}


def test_expiry_retries_until_max_attempts_then_fails(ctl, clock):
    _, body = ctl.create_task(task_body(max_attempts=2))
    for _ in range(2):
        lease = ctl.claim({"worker_id": "w1"})
        ctl.start({"dispatch_id": lease["dispatch_id"]})
        pass_time(ctl, clock, 6.01)
    seq = types(ctl, body["task_id"])
    assert seq.count("LEASE_EXPIRED") == 2 and seq.count("TASK_RETRY_SCHEDULED") == 1 and seq[-1] == "TASK_FAILED"
    expiries = [e for e in ctl.journal.events(task_id=body["task_id"]) if e.type.value == "LEASE_EXPIRED"]
    assert {e.payload["reason"] for e in expiries} == {"ttl"}


def test_lease_does_not_expire_exactly_at_the_heartbeat_boundary(ctl, clock):
    ctl.create_task(task_body())
    lease = ctl.claim({"worker_id": "w1"})
    pass_time(ctl, clock, 5.99)
    assert ctl.journal.task(lease["task_id"]).status is TaskStatus.CLAIMED


def test_non_idempotent_started_attempt_is_blocked_not_retried(ctl, clock):
    _, body = ctl.create_task(task_body(effect_class="non_idempotent"))
    lease = ctl.claim({"worker_id": "w1"})
    ctl.start({"dispatch_id": lease["dispatch_id"]})
    pass_time(ctl, clock, 10)
    assert types(ctl, body["task_id"])[-2:] == ["LEASE_EXPIRED", "TASK_BLOCKED"]
    assert ctl.claim({"worker_id": "w2"}) is None
    assert types(ctl, body["task_id"]).count("TASK_CLAIMED") == 1


def test_non_idempotent_attempt_that_never_started_is_retried(ctl, clock):
    _, body = ctl.create_task(task_body(effect_class="non_idempotent"))
    ctl.claim({"worker_id": "w1"})
    pass_time(ctl, clock, 10)
    assert types(ctl, body["task_id"])[-1] == "TASK_RETRY_SCHEDULED"
    assert ctl.claim({"worker_id": "w2"})["attempt"] == 2


def test_suspend_gap_does_not_expire_leases(ctl, clock):
    ctl.create_task(task_body())
    lease = ctl.claim({"worker_id": "w1"})
    ctl.tick()
    clock.advance(3600)  # laptop slept for an hour: one huge tick gap
    ctl.tick()
    assert ctl.journal.task(lease["task_id"]).status is TaskStatus.CLAIMED
    pass_time(ctl, clock, 6.5)
    assert ctl.journal.task(lease["task_id"]).status is TaskStatus.QUEUED


# --------------------------------------------------- I. result and verify
def test_duplicate_result_is_acknowledged_without_new_events(ctl):
    _, body = ctl.create_task(task_body())
    lease = run_attempt(ctl)
    ctl.drain()
    before = ctl.journal.head()
    status, answer = ctl.result(result_body(lease["dispatch_id"]))
    assert (status, answer["status"]) == (200, "ACK_DUPLICATE")
    assert ctl.journal.head() == before


def test_result_id_reuse_with_other_content_conflicts(ctl):
    ctl.create_task(task_body())
    lease = run_attempt(ctl)
    assert api_error(ctl.result, result_body(lease["dispatch_id"], sha="0" * 64)).status == 409


def test_result_before_start_is_refused(ctl):
    ctl.create_task(task_body())
    lease = ctl.claim({"worker_id": "w1"})
    err = api_error(ctl.result, result_body(lease["dispatch_id"]))
    assert (err.status, err.code) == (409, "not_started")


def test_late_result_from_superseded_attempt_is_discarded(ctl, clock):
    _, body = ctl.create_task(task_body())
    stale = ctl.claim({"worker_id": "w1"})
    ctl.start({"dispatch_id": stale["dispatch_id"]})
    pass_time(ctl, clock, 7)
    run_attempt(ctl, worker="w2", result_id="r2")
    ctl.drain()
    for _ in range(2):  # a repeated stale post must not grow the journal
        err = api_error(ctl.result, result_body(stale["dispatch_id"], result_id="late-1"))
        assert err.status == 409 and err.code == "stale_dispatch"
    seq = types(ctl, body["task_id"])
    assert seq.count("LATE_RESULT_DISCARDED") == 1 and seq.count("RESULT_ACCEPTED") == 1
    accepted = [e for e in ctl.journal.events(task_id=body["task_id"]) if e.type.value == "RESULT_ACCEPTED"]
    assert accepted[0].attempt == 2 and accepted[0].result_id == "r2"


def test_failure_outcome_is_rejected_and_retried(ctl):
    _, body = ctl.create_task(task_body())
    run_attempt(ctl, outcome="failure", result_id="r1")
    ctl.drain()
    run_attempt(ctl, result_id="r2")
    ctl.drain()
    seq = types(ctl, body["task_id"])
    assert seq.count("RESULT_REJECTED") == 1 and seq[-1] == "TASK_COMPLETE"


def test_non_retryable_failure_fails_the_task(ctl):
    _, body = ctl.create_task(task_body())
    lease = ctl.claim({"worker_id": "w1"})
    ctl.start({"dispatch_id": lease["dispatch_id"]})
    ctl.result(result_body(lease["dispatch_id"], outcome="failure", retryable=False, reason="bad input"))
    ctl.drain()
    assert types(ctl, body["task_id"])[-2:] == ["RESULT_REJECTED", "TASK_FAILED"]


@pytest.mark.parametrize("verifier, reason", [
    (Verifiers(), "no verifier"),
    (Verifiers(probe=lambda t, r, h: 1 / 0), "raised"),
    (Verifiers(probe=lambda t, r, h: True), "invalid verdict"),
    (Verifiers(probe=sha_matches), "sha mismatch"),
])
def test_verification_fails_closed(tmp_path, verifier, reason):
    ctl = make_controller(tmp_path / "home", verifier=verifier)
    try:
        _, body = ctl.create_task(task_body())
        lease = ctl.claim({"worker_id": "w1"})
        ctl.start({"dispatch_id": lease["dispatch_id"]})
        ctl.result(result_body(lease["dispatch_id"], sha="1" * 64))
        ctl.drain()
        seq = types(ctl, body["task_id"])
        assert "RESULT_ACCEPTED" not in seq and "TASK_COMPLETE" not in seq and seq[-1] == "TASK_FAILED"
        rejected = next(e for e in ctl.journal.events(task_id=body["task_id"]) if e.type.value == "RESULT_REJECTED")
        assert reason in rejected.payload["reason"]
    finally:
        ctl.stop()


def test_retryable_verdict_retries(tmp_path):
    verdicts = iter([Verdict(False, "provider busy", retryable=True), Verdict(True, "ok")])
    ctl = make_controller(tmp_path / "home", verifier=Verifiers(probe=lambda t, r, h: next(verdicts)))
    try:
        _, body = ctl.create_task(task_body())
        run_attempt(ctl, result_id="r1")
        ctl.drain()
        run_attempt(ctl, result_id="r2")
        ctl.drain()
        assert types(ctl, body["task_id"])[-1] == "TASK_COMPLETE"
        assert ctl.journal.task(body["task_id"]).attempt == 2
    finally:
        ctl.stop()


# ---------------------------------------------------------------- J. cancel
def test_cancel_of_queued_task_is_immediate(ctl):
    _, body = ctl.create_task(task_body())
    assert ctl.cancel(body["task_id"])["status"] == "CANCELLED"
    assert ctl.claim({"worker_id": "w1"}) is None
    assert api_error(ctl.cancel, body["task_id"]).status == 409
    assert api_error(ctl.cancel, "task-unknown").status == 404


def test_cancel_running_task_needs_worker_confirmation(ctl):
    _, body = ctl.create_task(task_body())
    lease = ctl.claim({"worker_id": "w1"})
    ctl.start({"dispatch_id": lease["dispatch_id"]})
    assert ctl.cancel(body["task_id"])["status"] == "RUNNING"
    answer = ctl.heartbeat({"worker_id": "w1", "dispatch_ids": [lease["dispatch_id"]]})
    assert answer["cancel"] == [lease["dispatch_id"]]
    err = api_error(ctl.result, result_body(lease["dispatch_id"]))
    assert err.code == "cancel_requested"
    ctl.heartbeat({"worker_id": "w1", "dispatch_ids": []})  # tree reaped -> confirmation
    seq = types(ctl, body["task_id"])
    assert seq[-2:] == ["TASK_CANCEL_REQUESTED", "TASK_CANCELLED"]
    assert "RESULT_READY" not in seq
    assert api_error(ctl.result, result_body(lease["dispatch_id"])).status == 409
    assert api_error(ctl.cancel, body["task_id"]).status == 409


def test_cancel_of_claimed_task_resolves_on_lease_expiry(ctl, clock):
    _, body = ctl.create_task(task_body())
    lease = ctl.claim({"worker_id": "w1"})
    ctl.cancel(body["task_id"])
    assert api_error(ctl.start, {"dispatch_id": lease["dispatch_id"]}).code == "cancel_requested"
    pass_time(ctl, clock, 7)
    assert types(ctl, body["task_id"])[-2:] == ["LEASE_EXPIRED", "TASK_CANCELLED"]


def test_cancel_of_blocked_task(ctl, clock):
    _, body = ctl.create_task(task_body(effect_class="non_idempotent"))
    lease = ctl.claim({"worker_id": "w1"})
    ctl.start({"dispatch_id": lease["dispatch_id"]})
    pass_time(ctl, clock, 7)
    assert ctl.cancel(body["task_id"])["status"] == "CANCELLED"


# -------------------------------------------------- projection stays derived
def test_projection_always_equals_replay(ctl, clock):
    for effect in ("idempotent", "non_idempotent"):
        ctl.create_task(task_body(effect_class=effect))
    run_attempt(ctl)
    lease = ctl.claim({"worker_id": "w2"})
    ctl.start({"dispatch_id": lease["dispatch_id"]})
    pass_time(ctl, clock, 7)
    ctl.drain()
    assert ctl.journal.verify_projection() and ctl.journal.verify_chain().ok
    assert projection_hash(ctl.journal.conn)

