"""L2 final hardening: fail-safe effect classes, Human Desk decisions, attribution, effect key."""

import hashlib
import sqlite3
import sys
import types as pytypes
from dataclasses import replace

import pytest

from ctrl_helpers import (
    FakeClock, LiveService, Verifiers, make_controller, result_body, run_attempt, task_body, types,
)
from courier_core import build
from courier_core.controller import ApiError
from courier_core.events import EFFECT_CLASSES, Event, EventType, EventValidationError, effect_key
from courier_core.journal import Journal
from courier_core.projection import PROJECTION_VERSION, fold, projection_hash
from courier_core.state_machine import (
    Decision, TaskStatus, TransitionError, apply, decide_after_failure, may_auto_retry,
)
from courier_core.verification import Verdict

UNKNOWN_CLASSES = ["physical", "medical", "aviation", "financial", "legal", "future_custom_class", "", "Idempotent"]


def pass_time(ctl, clock, seconds, step=0.25):
    for _ in range(int(seconds / step)):
        clock.advance(step)
        ctl.tick()


def api_error(fn, *args):
    with pytest.raises(ApiError) as info:
        fn(*args)
    return info.value


def blocked_task(ctl, clock, **overrides):
    """A started non-idempotent attempt whose worker vanished: BLOCKED."""
    _, body = ctl.create_task(task_body(effect_class="non_idempotent", lease_ttl_s=3, **overrides))
    lease = ctl.claim({"worker_id": "w1"})
    ctl.start({"dispatch_id": lease["dispatch_id"]})
    pass_time(ctl, clock, 4)
    assert ctl.journal.task(body["task_id"]).status is TaskStatus.BLOCKED
    return body["task_id"], lease


def decide(task_id, decision, attempt=1, actor="desk:ana", reason="checked the provider dashboard"):
    return {"decision": decision, "actor": actor, "attempt": attempt, "reason": reason}


def assert_projection_is_replay(ctl):
    assert fold(ctl.journal.events()) == {t.task_id: t for t in ctl.journal.tasks()}
    assert ctl.journal.verify_chain().ok


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def ctl(tmp_path, clock):
    controller = make_controller(tmp_path / "home", clock=clock)
    yield controller
    controller.stop()


# ============================================================ 1. fail-safe effect class
def lost_attempt(effect_class, cancel_requested=False, attempt=1, max_attempts=3):
    """Pure state: a started attempt whose lease was lost."""
    events = [Event(type=EventType.TASK_CREATED, task_id="t1", payload={
        "adapter": "synthetic", "params": {}, "effect_class": "idempotent", "max_attempts": max_attempts,
        "lease_ttl_s": 6})]
    state = None
    for event in events:
        state = apply(state, event)
    # A class this build cannot create may still arrive from a newer journal or a
    # future schema: the decision must not depend on the intake whitelist.
    return replace(state, status=TaskStatus.RETRY_PENDING, effect_class=effect_class, attempt=attempt,
                   started=True, failure_kind="lease_lost", cancel_requested=cancel_requested)


def test_only_idempotent_is_on_the_auto_retry_whitelist():
    assert may_auto_retry("idempotent")
    for effect_class in ["non_idempotent", *UNKNOWN_CLASSES]:
        assert not may_auto_retry(effect_class), effect_class


def test_idempotent_uncertain_outcome_follows_bounded_retry():
    assert decide_after_failure(lost_attempt("idempotent")) is Decision.RETRY
    assert decide_after_failure(lost_attempt("idempotent", attempt=3, max_attempts=3)) is Decision.FAIL
    assert decide_after_failure(lost_attempt("idempotent", cancel_requested=True)) is Decision.CANCEL


@pytest.mark.parametrize("effect_class", ["non_idempotent", *UNKNOWN_CLASSES])
def test_uncertain_outcome_of_any_other_class_is_blocked(effect_class):
    state = lost_attempt(effect_class)
    assert decide_after_failure(state) is Decision.BLOCK
    retry = Event(type=EventType.TASK_RETRY_SCHEDULED, task_id="t1", attempt=1, payload={"reason": "x"})
    with pytest.raises(TransitionError, match="retry forbidden"):
        apply(state, retry)
    with pytest.raises(TransitionError, match="must be BLOCKED"):
        apply(state, Event(type=EventType.TASK_FAILED, task_id="t1", payload={"reason": "x"}))


@pytest.mark.parametrize("effect_class", ["non_idempotent", *UNKNOWN_CLASSES])
def test_cancel_does_not_erase_uncertainty(effect_class):
    state = lost_attempt(effect_class, cancel_requested=True)
    assert decide_after_failure(state) is Decision.BLOCK
    with pytest.raises(TransitionError, match="BLOCKED before it can be cancelled"):
        apply(state, Event(type=EventType.TASK_CANCELLED, task_id="t1", payload={"actor": "desk:ana"}))


@pytest.mark.parametrize("effect_class", UNKNOWN_CLASSES)
def test_unknown_effect_class_is_refused_at_intake(ctl, effect_class):
    assert effect_class not in EFFECT_CLASSES
    assert api_error(ctl.create_task, task_body(effect_class=effect_class)).status == 400
    with pytest.raises(EventValidationError):
        Event(type=EventType.TASK_CREATED, task_id="t1", payload={
            "adapter": "a", "params": {}, "effect_class": effect_class, "max_attempts": 1, "lease_ttl_s": 1})
    assert ctl.journal.tasks() == []


def test_worker_failure_is_retryable_by_omission_only_for_idempotent(ctl):
    _, idem = ctl.create_task(task_body(effect_class="idempotent"))
    run_attempt(ctl, outcome="failure")
    ctl.drain()
    assert types(ctl, idem["task_id"])[-2:] == ["RESULT_REJECTED", "TASK_RETRY_SCHEDULED"]

    run_attempt(ctl, outcome="success", result_id="r2")  # finish it so the queue is clear
    ctl.drain()
    _, unsafe = ctl.create_task(task_body(effect_class="non_idempotent"))
    run_attempt(ctl, outcome="failure", result_id="r3")
    ctl.drain()
    task = ctl.journal.task(unsafe["task_id"])
    assert task.status is TaskStatus.FAILED and task.attempt == 1
    rejected = [e for e in ctl.journal.events(task_id=unsafe["task_id"]) if e.type is EventType.RESULT_REJECTED]
    assert rejected[0].payload["retryable"] is False


def test_explicitly_retryable_worker_failure_of_non_idempotent_task_retries(ctl):
    _, body = ctl.create_task(task_body(effect_class="non_idempotent"))
    lease = ctl.claim({"worker_id": "w1"})
    ctl.start({"dispatch_id": lease["dispatch_id"]})
    ctl.result(result_body(lease["dispatch_id"], outcome="failure", retryable=True, reason="provider said 503"))
    ctl.drain()
    assert types(ctl, body["task_id"])[-2:] == ["RESULT_REJECTED", "TASK_RETRY_SCHEDULED"]


# ============================================================ 2. Human Desk decisions
def test_effect_confirmed_completes_without_re_executing(ctl, clock):
    task_id, _ = blocked_task(ctl, clock)
    answer = ctl.resolve(task_id, decide(task_id, "effect_confirmed"))
    assert answer == {"status": "COMPLETE", "decision": "effect_confirmed", "duplicate": False}
    task = ctl.journal.task(task_id)
    assert task.resolution == "effect_confirmed" and task.decided_by == "desk:ana"
    assert task.accepted_result_id is None  # a human attestation is never a verified result
    assert ctl.claim({"worker_id": "w2"}) is None
    kinds = types(ctl, task_id)
    assert kinds.count("TASK_CLAIMED") == 1 and "RESULT_ACCEPTED" not in kinds
    event = [e for e in ctl.journal.events(task_id=task_id) if e.type is EventType.EFFECT_CONFIRMED][0]
    assert event.attempt == 1 and event.payload == {"actor": "desk:ana", "reason": "checked the provider dashboard"}
    assert_projection_is_replay(ctl)


def test_retry_authorized_grants_one_fresh_fenced_attempt(ctl, clock):
    task_id, old = blocked_task(ctl, clock, max_attempts=1)
    answer = ctl.resolve(task_id, decide(task_id, "retry_authorized", actor="desk:ben"))
    assert answer["status"] == "QUEUED"
    lease = ctl.claim({"worker_id": "w2"})
    assert lease["attempt"] == 2 and lease["dispatch_id"] != old["dispatch_id"]
    assert lease["spec"]["effect_key"] == old["spec"]["effect_key"] == effect_key(task_id)
    # The old dispatch is fenced off: its late report changes nothing.
    assert api_error(ctl.result, result_body(old["dispatch_id"], result_id="old")).code == "stale_dispatch"
    ctl.start({"dispatch_id": lease["dispatch_id"]})
    ctl.result(result_body(lease["dispatch_id"], result_id="r2"))
    ctl.drain()
    task = ctl.journal.task(task_id)
    assert task.status is TaskStatus.COMPLETE and task.resolution == "verified"
    assert task.decided_by == "desk:ben" and task.max_attempts == 2
    assert_projection_is_replay(ctl)


def test_authorized_retry_that_is_lost_again_blocks_again(ctl, clock):
    task_id, _ = blocked_task(ctl, clock)
    ctl.resolve(task_id, decide(task_id, "retry_authorized"))
    lease = ctl.claim({"worker_id": "w2"})
    ctl.start({"dispatch_id": lease["dispatch_id"]})
    pass_time(ctl, clock, 4)
    assert ctl.journal.task(task_id).status is TaskStatus.BLOCKED
    assert types(ctl, task_id).count("TASK_BLOCKED") == 2
    # A stale click on the first block cannot act on the second one.
    assert ctl.resolve(task_id, decide(task_id, "retry_authorized"))["duplicate"] is True
    assert ctl.journal.task(task_id).status is TaskStatus.BLOCKED
    err = api_error(ctl.resolve, task_id, decide(task_id, "effect_confirmed", attempt=1))
    assert (err.status, err.code, err.extra["attempt"]) == (409, "stale_decision", 2)
    assert ctl.resolve(task_id, decide(task_id, "effect_confirmed", attempt=2))["status"] == "COMPLETE"


def test_resolve_cancel_records_the_actor_and_keeps_the_uncertainty(ctl, clock):
    task_id, _ = blocked_task(ctl, clock)
    answer = ctl.resolve(task_id, decide(task_id, "cancel", reason="customer withdrew"))
    assert answer == {"status": "CANCELLED", "decision": "cancel", "duplicate": False}
    task = ctl.journal.task(task_id)
    assert task.resolution == "cancelled_effect_unknown" and task.decided_by == "desk:ana"
    assert "unknown" in task.last_reason  # the block reason survives the cancellation
    for event in ctl.journal.events(task_id=task_id):
        if event.type in (EventType.TASK_CANCEL_REQUESTED, EventType.TASK_CANCELLED):
            assert event.payload["actor"] == "desk:ana"
    assert api_error(ctl.resolve, task_id, decide(task_id, "cancel")).code == "not_blocked"


def test_decisions_need_actor_reason_attempt_and_a_blocked_task(ctl, clock):
    task_id, _ = blocked_task(ctl, clock)
    _, plain = ctl.create_task(task_body())
    assert api_error(ctl.resolve, plain["task_id"], decide(plain["task_id"], "effect_confirmed")).code == "not_blocked"
    assert api_error(ctl.resolve, "task-missing", decide("x", "effect_confirmed")).status == 404
    for bad in ({"decision": "approve"}, {"actor": None}, {"actor": ""}, {"actor": "x" * 201},
                {"reason": ""}, {"reason": "   "}, {"reason": None}, {"attempt": None}, {"attempt": 0},
                {"attempt": True}, {"extra": 1}):
        body = {**decide(task_id, "effect_confirmed"), **bad}
        body = {k: v for k, v in body.items() if v is not None}
        assert api_error(ctl.resolve, task_id, body).status == 400, bad
    assert api_error(ctl.resolve, task_id, [1]).status == 400
    assert ctl.journal.task(task_id).status is TaskStatus.BLOCKED


def test_repeated_decision_is_acknowledged_and_a_conflicting_one_refused(ctl, clock):
    task_id, _ = blocked_task(ctl, clock)
    first = ctl.resolve(task_id, decide(task_id, "effect_confirmed"))
    again = ctl.resolve(task_id, decide(task_id, "effect_confirmed"))
    assert first["duplicate"] is False and again == {"status": "COMPLETE", "decision": "effect_confirmed",
                                                     "duplicate": True}
    assert api_error(ctl.resolve, task_id, decide(task_id, "effect_confirmed", actor="desk:eve")).code \
        == "decision_conflict"
    assert api_error(ctl.resolve, task_id, decide(task_id, "retry_authorized")).code == "not_blocked"
    assert types(ctl, task_id).count("EFFECT_CONFIRMED") == 1


def test_retry_is_not_authorized_over_a_pending_cancel_request(ctl, clock):
    _, body = ctl.create_task(task_body(effect_class="non_idempotent", lease_ttl_s=3))
    lease = ctl.claim({"worker_id": "w1"})
    ctl.start({"dispatch_id": lease["dispatch_id"]})
    ctl.cancel(body["task_id"])
    pass_time(ctl, clock, 4)
    task_id = body["task_id"]
    assert ctl.journal.task(task_id).status is TaskStatus.BLOCKED
    assert api_error(ctl.resolve, task_id, decide(task_id, "retry_authorized")).code == "cancel_requested"
    assert ctl.resolve(task_id, decide(task_id, "effect_confirmed"))["status"] == "COMPLETE"


def test_late_result_for_a_blocked_task_is_kept_as_evidence(ctl, clock):
    task_id, old = blocked_task(ctl, clock)
    err = api_error(ctl.result, result_body(old["dispatch_id"], result_id="late-1", reason="paid, receipt 42"))
    assert err.code == "stale_dispatch"
    assert ctl.journal.task(task_id).status is TaskStatus.BLOCKED
    late = [e for e in ctl.journal.events(task_id=task_id) if e.type is EventType.LATE_RESULT_DISCARDED][0]
    assert late.payload["outcome"] == "success" and late.payload["attempt"] == 1
    assert late.payload["artifacts"][0]["path"] == "out.txt"
    assert late.payload["reported_reason"] == "paid, receipt 42"


def test_human_decisions_survive_restart_and_replay(tmp_path, clock):
    home = tmp_path / "home"
    ctl = make_controller(home, clock=clock)
    confirmed, _ = blocked_task(ctl, clock)
    retried, _ = blocked_task(ctl, clock)
    cancelled, _ = blocked_task(ctl, clock)
    ctl.resolve(confirmed, decide(confirmed, "effect_confirmed"))
    ctl.resolve(retried, decide(retried, "retry_authorized"))
    ctl.resolve(cancelled, decide(cancelled, "cancel"))
    live_hash = projection_hash(ctl.journal.conn)
    ctl.stop()
    again = make_controller(home, clock=FakeClock())
    try:
        assert projection_hash(again.journal.conn) == live_hash
        assert_projection_is_replay(again)
        assert again.journal.task(retried).status is TaskStatus.QUEUED
        assert again.claim({"worker_id": "w9"})["task_id"] == retried
    finally:
        again.stop()


def test_state_machine_refuses_decisions_outside_blocked_and_without_actor():
    created = Event(type=EventType.TASK_CREATED, task_id="t1", payload={
        "adapter": "a", "params": {}, "effect_class": "non_idempotent", "max_attempts": 1, "lease_ttl_s": 1})
    queued = apply(None, created)
    for event_type in (EventType.EFFECT_CONFIRMED, EventType.RETRY_AUTHORIZED):
        with pytest.raises(TransitionError, match="only a blocked task"):
            apply(queued, Event(type=event_type, task_id="t1", attempt=1, payload={"actor": "a", "reason": "r"}))
        for payload in ({"reason": "r"}, {"actor": "", "reason": "r"}, {"actor": "a", "reason": " "},
                        {"actor": 7, "reason": "r"}):
            with pytest.raises(EventValidationError):
                Event(type=event_type, task_id="t1", attempt=1, payload=payload)
        with pytest.raises(EventValidationError):
            Event(type=event_type, task_id="t1", payload={"actor": "a", "reason": "r"})


def test_resolve_and_cancel_over_http(tmp_path):
    clock = FakeClock()
    live = LiveService(tmp_path / "home", clock=clock)
    try:
        ctl = live.controller
        task_id, _ = blocked_task(ctl, clock)
        refused = live.post(f"/v1/tasks/{task_id}/cancel")
        assert refused.status_code == 409 and refused.json()["error"] == "actor_required"
        answer = live.post(f"/v1/tasks/{task_id}/resolve", decide(task_id, "effect_confirmed"))
        assert answer.status_code == 200 and answer.json()["status"] == "COMPLETE"
        view = live.get(f"/v1/tasks/{task_id}").json()
        assert view["resolution"] == "effect_confirmed" and view["decided_by"] == "desk:ana"
        assert view["effect_key"] == effect_key(task_id)
        assert live.post(f"/v1/tasks/{task_id}/resolve", {"decision": "x"}).status_code == 400
        assert live.post("/v1/tasks/task-nope/resolve", decide("x", "cancel")).status_code == 404
        second, _ = blocked_task(ctl, clock)
        done = live.post(f"/v1/tasks/{second}/cancel", {"actor": "desk:ana", "reason": "stop"})
        assert done.status_code == 200 and done.json()["status"] == "CANCELLED"
    finally:
        live.stop()


# ============================================================ 3. build / verifier identity
def test_controller_start_records_build_identity(tmp_path, monkeypatch):
    monkeypatch.setenv("COURIER_BUILD_ID", "v1.0.0-rc1+abc123")
    ctl = make_controller(tmp_path / "home")
    try:
        started = [e for e in ctl.journal.events() if e.type is EventType.CONTROLLER_STARTED][0]
        recorded = started.payload["build"]
        assert recorded["build_id"] == "v1.0.0-rc1+abc123"
        assert recorded["version"] == "1.0.0.dev0"
        assert recorded["source_sha256"] == build.source_sha256() and len(recorded["source_sha256"]) == 64
        assert ctl.health()["build"] == recorded
    finally:
        ctl.stop()


def test_every_event_is_attributed_to_the_build_that_wrote_it(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("COURIER_BUILD_ID", "build-A")
    first = make_controller(home)
    _, body = first.create_task(task_body())
    first.stop()
    monkeypatch.setenv("COURIER_BUILD_ID", "build-B")
    second = make_controller(home)
    try:
        run_attempt(second)
        second.drain()
        events = list(second.journal.events())
        by_type = {e.type: e for e in events if e.task_id == body["task_id"]}
        assert build.build_for_seq(events, by_type[EventType.TASK_CREATED].seq)["build_id"] == "build-A"
        assert build.build_for_seq(events, by_type[EventType.TASK_COMPLETE].seq)["build_id"] == "build-B"
        assert fold(events) == {t.task_id: t for t in second.journal.tasks()}
    finally:
        second.stop()


def test_build_identity_does_not_change_the_projection_hash(tmp_path, monkeypatch):
    hashes = []
    for build_id in ("one", "two"):
        monkeypatch.setenv("COURIER_BUILD_ID", build_id)
        ctl = make_controller(tmp_path / build_id)
        try:
            ctl.create_task(task_body(idempotency_key="same"))
            hashes.append(projection_hash(ctl.journal.conn))
        finally:
            ctl.stop()
    assert hashes[0] == hashes[1]


def test_accepted_result_names_the_verifier_that_accepted_it(tmp_path, monkeypatch):
    module = pytypes.ModuleType("probe_verifier_v7")
    module.VERIFIER_VERSION = "7.1"
    module.__file__ = __file__

    def verify(task, result, home):
        return Verdict(True, "evidence ok")
    verify.__module__ = module.__name__
    module.verify = verify
    monkeypatch.setitem(sys.modules, module.__name__, module)
    ctl = make_controller(tmp_path / "home", verifier=lambda adapter: verify if adapter == "probe" else None)
    try:
        _, body = ctl.create_task(task_body())
        run_attempt(ctl)
        ctl.drain()
        accepted = [e for e in ctl.journal.events(task_id=body["task_id"])
                    if e.type is EventType.RESULT_ACCEPTED][0]
        verifier = accepted.payload["verifier"]
        assert verifier["kind"] == "adapter" and verifier["version"] == "7.1"
        assert verifier["name"].startswith("probe_verifier_v7.") and verifier["name"].endswith(".verify")
        assert verifier["source_sha256"] == hashlib.sha256(open(__file__, "rb").read()).hexdigest()
        assert ctl.journal.task(body["task_id"]).resolution == "verified"
    finally:
        ctl.stop()


def test_real_adapter_verifier_identity_carries_source_hash(tmp_path, monkeypatch):
    package = tmp_path / "pkg" / "adapters"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    source = ("from courier_core.verification import Verdict\nVERIFIER_VERSION = '2'\n"
              "def verify(task, result, home):\n    return Verdict(True, 'ok')\n")
    (package / "idprobe.py").write_text(source)
    monkeypatch.syspath_prepend(str(tmp_path / "pkg"))
    for name in [n for n in sys.modules if n == "adapters" or n.startswith("adapters.")]:
        monkeypatch.delitem(sys.modules, name)
    from courier_core.controller import Controller
    ctl = Controller(tmp_path / "home", clock=FakeClock()).boot()
    try:
        _, body = ctl.create_task(task_body(adapter="idprobe"))
        run_attempt(ctl)
        ctl.drain()
        accepted = [e for e in ctl.journal.events(task_id=body["task_id"])
                    if e.type is EventType.RESULT_ACCEPTED][0]
        assert accepted.payload["verifier"] == {
            "kind": "adapter", "name": "adapters.idprobe.verify", "version": "2",
            "source_sha256": hashlib.sha256(source.encode()).hexdigest()}
    finally:
        ctl.stop()


@pytest.mark.parametrize("case, rule", [("no_verifier", "no_verifier"), ("failure", "worker_reported_failure")])
def test_rejections_name_the_courier_rule_that_decided(tmp_path, case, rule):
    ctl = make_controller(tmp_path / "home", verifier=Verifiers())
    try:
        _, body = ctl.create_task(task_body(max_attempts=1))
        run_attempt(ctl, outcome="failure" if case == "failure" else "success")
        ctl.drain()
        rejected = [e for e in ctl.journal.events(task_id=body["task_id"])
                    if e.type is EventType.RESULT_REJECTED][0]
        assert rejected.payload["verifier"] == {"kind": "courier_rule", "name": rule, "adapter": "probe"}
    finally:
        ctl.stop()


def test_malformed_verdicts_still_fail_closed_with_identity(tmp_path):
    def sneaky(task, result, home):
        return Verdict(1, "truthy is not True")
    ctl = make_controller(tmp_path / "home", verifier=Verifiers(probe=sneaky))
    try:
        _, body = ctl.create_task(task_body(max_attempts=1))
        run_attempt(ctl)
        ctl.drain()
        task = ctl.journal.task(body["task_id"])
        assert task.status is TaskStatus.FAILED and task.resolution is None
    finally:
        ctl.stop()


# ============================================================ 4. stable effect key
def test_effect_key_is_stable_per_task_and_distinct_between_tasks(ctl, clock):
    _, one = ctl.create_task(task_body(lease_ttl_s=3))
    first = ctl.claim({"worker_id": "w1"})
    ctl.start({"dispatch_id": first["dispatch_id"]})
    pass_time(ctl, clock, 4)  # idempotent: retried automatically
    second = ctl.claim({"worker_id": "w2"})
    assert second["task_id"] == one["task_id"] and second["attempt"] == 2
    assert first["spec"]["effect_key"] == second["spec"]["effect_key"] == effect_key(one["task_id"])
    _, other = ctl.create_task(task_body())
    assert effect_key(other["task_id"]) != effect_key(one["task_id"])
    assert effect_key("task-x") == effect_key("task-x")
    key = effect_key("task-x")
    assert key.startswith("cfx-") and len(key) == 44 and key[4:].isalnum()


def test_effect_key_survives_restart_and_idempotent_resubmission(tmp_path):
    home = tmp_path / "home"
    ctl = make_controller(home)
    _, body = ctl.create_task(task_body(idempotency_key="order-77"))
    before = ctl.claim({"worker_id": "w1"})["spec"]["effect_key"]
    ctl.stop()
    again = make_controller(home)
    try:
        status, repeat = again.create_task(task_body(idempotency_key="order-77"))
        assert status == 200 and repeat["task_id"] == body["task_id"]
        assert again.task_view(body["task_id"])["effect_key"] == before
    finally:
        again.stop()


# ============================================================ projection from an older build
def test_projection_from_an_older_build_is_rebuilt_from_the_journal(tmp_path, clock):
    home = tmp_path / "home"
    ctl = make_controller(home, clock=clock)
    task_id, _ = blocked_task(ctl, clock)
    ctl.resolve(task_id, decide(task_id, "effect_confirmed"))
    head = ctl.journal.head()
    expected = projection_hash(ctl.journal.conn)
    ctl.stop()
    conn = sqlite3.connect(home / "courier.db")
    conn.execute("ALTER TABLE tasks DROP COLUMN resolution")
    conn.execute("ALTER TABLE tasks DROP COLUMN decided_by")
    conn.execute("UPDATE projection_meta SET value = '1' WHERE key = 'version'")
    conn.commit()
    conn.close()
    again = make_controller(home)
    try:
        assert again.mode == "normal"
        assert again.journal.head()[0] == head[0] + 2  # only CONTROLLER_STOPPED + CONTROLLER_STARTED
        assert list(again.journal.events())[head[0] - 1].hash == head[1]
        assert projection_hash(again.journal.conn) == expected
        assert again.journal.task(task_id).resolution == "effect_confirmed"
        meta = again.journal.conn.execute("SELECT value FROM projection_meta WHERE key='version'").fetchone()
        assert meta[0] == str(PROJECTION_VERSION)
    finally:
        again.stop()


def test_stale_projection_on_a_damaged_journal_stays_read_only(tmp_path):
    home = tmp_path / "home"
    ctl = make_controller(home)
    _, body = ctl.create_task(task_body())
    ctl.stop()
    conn = sqlite3.connect(home / "courier.db")
    conn.execute("UPDATE projection_meta SET value = '1' WHERE key = 'version'")
    conn.execute("DROP TRIGGER events_no_update")
    conn.commit()
    conn.close()
    before = (home / "courier.db").read_bytes()
    again = make_controller(home)
    try:
        assert again.mode == "degraded_readonly"
        err = api_error(again.task_view, body["task_id"])
        assert err.status == 503
    finally:
        again.stop()
    assert (home / "courier.db").read_bytes() == before


def test_journal_open_rebuilds_a_stale_projection_atomically(tmp_path):
    path = tmp_path / "courier.db"
    with Journal(path) as journal:
        journal.append(Event(type=EventType.TASK_CREATED, task_id="t1", payload={
            "adapter": "a", "params": {}, "effect_class": "idempotent", "max_attempts": 1, "lease_ttl_s": 1}))
    conn = sqlite3.connect(path)
    conn.execute("DELETE FROM tasks")
    conn.execute("UPDATE projection_meta SET value = '0' WHERE key = 'version'")
    conn.commit()
    conn.close()
    with Journal(path) as journal:
        assert journal.projection_current() and journal.verify_projection()
        assert journal.task("t1").status is TaskStatus.QUEUED
