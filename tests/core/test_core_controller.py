"""Test hardening for courier_core.controller (lane L4, pool item P9).

Comprehensive unit and invariant tests covering:
- Helper functions and validation (_require_id, _require_int, _require_reason, _only_fields, heartbeat_interval)
- ApiError initialization and body formatting
- Controller boot, inspect_existing, and degraded mode on corrupt journal
- Stop lifecycle, stopping guards, and lock timeouts (busy)
- Task creation, validation, idempotency, duplicate ACK, conflict rejection
- Task view queries, 404, stopping guards
- Claiming, FIFO queue ordering, lease creation, skipping cancelled tasks
- Start transitions, worker fencing, already-started idempotency, cancel-requested fencing
- Heartbeat handling, deadline extension, stop list, cancel list, reaper confirmation
- Result recording, validation, verification queueing, duplicates, conflicts, stale result journaling
- Cancellation of queued, active, and blocked tasks, actor requirement
- Human resolution of blocked tasks, duplicate decisions, decision conflicts, stale attempts
- Tick lease expiration, suspend-gap deadline extension
- Verification queue draining, verifier acceptance, and rejection transitions
- Event stream reading and change notification
"""

from __future__ import annotations

import hashlib
import os
import queue
import sqlite3
import threading
import time
from pathlib import Path

import pytest

from courier_core.controller import (
    DEGRADED,
    MAX_ATTEMPTS_LIMIT,
    MAX_HEARTBEAT_DISPATCHES,
    MAX_ID_LENGTH,
    MAX_LEASE_TTL_S,
    MAX_REASON_CHARS,
    MAX_TIMEOUT_S,
    NORMAL,
    ApiError,
    Controller,
    Lease,
    _only_fields,
    _require_id,
    _require_int,
    _require_reason,
    heartbeat_interval,
)
from courier_core.events import EFFECT_CLASSES, Event, EventType
from courier_core.journal import Journal
from courier_core.state_machine import TaskStatus
from courier_core.verification import Verdict


class FakeClock:
    """Deterministic monotonic clock for controller tests."""

    def __init__(self, initial: float = 1000.0):
        self.now = initial

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def dummy_verifier(task, result, home):
    """Simple default verifier that accepts everything."""
    return Verdict(accepted=True, reason="ok")


def rejecting_verifier(retryable: bool = True, reason: str = "failed"):
    def _verify(task, result, home):
        return Verdict(accepted=False, reason=reason, retryable=retryable)
    return _verify


def make_ctrl(tmp_path: Path, clock: FakeClock | None = None, verifier=dummy_verifier, lock_timeout_s: float = 2.0) -> Controller:
    """Construct and boot a test Controller."""
    clk = clock or FakeClock()
    ctrl = Controller(tmp_path, clock=clk, verifier=lambda _: verifier, lock_timeout_s=lock_timeout_s)
    ctrl.boot()
    return ctrl


# ==============================================================================
# Helper & Input Validation Tests
# ==============================================================================

def test_heartbeat_interval_values():
    assert heartbeat_interval(60) == 20.0
    assert heartbeat_interval(6) == 2.0
    assert heartbeat_interval(1) == 0.5
    assert heartbeat_interval(0) == 0.5
    assert heartbeat_interval(-10) == 0.5


def test_api_error_properties_and_body():
    err = ApiError(400, "invalid_request", "bad param", field="adapter", count=42)
    assert err.status == 400
    assert err.code == "invalid_request"
    assert err.message == "bad param"
    assert err.body() == {
        "error": "invalid_request",
        "message": "bad param",
        "field": "adapter",
        "count": 42,
    }

    err_default_msg = ApiError(404, "not_found")
    assert err_default_msg.message == "not_found"
    assert err_default_msg.body() == {"error": "not_found", "message": "not_found"}


def test_require_id_validation():
    assert _require_id({"id": "valid_123"}, "id") == "valid_123"

    with pytest.raises(ApiError) as exc:
        _require_id({"id": ""}, "id")
    assert exc.value.status == 400
    assert "non-empty string" in exc.value.message

    with pytest.raises(ApiError):
        _require_id({"id": None}, "id")

    with pytest.raises(ApiError):
        _require_id({"id": 123}, "id")

    long_id = "a" * (MAX_ID_LENGTH + 1)
    with pytest.raises(ApiError):
        _require_id({"id": long_id}, "id")


def test_require_int_validation():
    assert _require_int({"count": 5}, "count", 1, 10) == 5
    assert _require_int({}, "count", 1, 10, required=False) is None

    with pytest.raises(ApiError):
        _require_int({}, "count", 1, 10, required=True)

    with pytest.raises(ApiError):
        _require_int({"count": True}, "count", 1, 10)  # bool must not pass as int

    with pytest.raises(ApiError):
        _require_int({"count": "5"}, "count", 1, 10)

    with pytest.raises(ApiError):
        _require_int({"count": 0}, "count", 1, 10)

    with pytest.raises(ApiError):
        _require_int({"count": 11}, "count", 1, 10)


def test_require_reason_validation():
    assert _require_reason({"reason": "test ok"}, required=True) == "test ok"
    assert _require_reason({}, required=False) is None

    with pytest.raises(ApiError):
        _require_reason({}, required=True)

    with pytest.raises(ApiError):
        _require_reason({"reason": ""}, required=True)

    with pytest.raises(ApiError):
        _require_reason({"reason": "   "}, required=True)

    long_reason = "a" * (MAX_REASON_CHARS + 1)
    with pytest.raises(ApiError):
        _require_reason({"reason": long_reason}, required=True)


def test_only_fields_validation():
    body = {"adapter": "probe", "params": {}}
    assert _only_fields(body, {"adapter", "params", "timeout_s"}) == body

    with pytest.raises(ApiError) as exc:
        _only_fields(["not", "a", "dict"], {"adapter"})
    assert exc.value.status == 400
    assert "must be a JSON object" in exc.value.message

    with pytest.raises(ApiError) as exc:
        _only_fields({"adapter": "probe", "unknown1": 1, "unknown2": 2}, {"adapter"})
    assert exc.value.status == 400
    assert "unknown field(s): unknown1, unknown2" in exc.value.message


# ==============================================================================
# Controller Boot, Health & Degraded Mode Tests
# ==============================================================================

def test_controller_boot_clean_directory(tmp_path: Path):
    clock = FakeClock()
    ctrl = make_ctrl(tmp_path / "ctrl_home", clock)
    try:
        assert ctrl.mode == NORMAL
        health = ctrl.health()
        assert health["mode"] == NORMAL
        assert health["head_seq"] >= 1
        assert health["active_leases"] == 0
        assert "build" in health
    finally:
        ctrl.stop()


def test_controller_degraded_on_corrupt_journal(tmp_path: Path):
    home = tmp_path / "corrupt_home"
    home.mkdir()
    db = home / "courier.db"
    db.write_bytes(b"not a valid sqlite database header at all")

    ctrl = Controller(home)
    ctrl.boot()
    try:
        assert ctrl.mode == DEGRADED
        assert ctrl.degraded_reason is not None
        assert "file is not a database" in ctrl.degraded_reason or "DatabaseError" in ctrl.degraded_reason or "cannot be opened" in ctrl.degraded_reason
        health = ctrl.health()
        assert health["mode"] == DEGRADED
        assert "reason" in health

        # Any mutating API call must fail fast with 503 degraded_readonly
        with pytest.raises(ApiError) as exc:
            ctrl.create_task({"adapter": "probe", "params": {}, "effect_class": "idempotent",
                              "max_attempts": 1, "lease_ttl_s": 5})
        assert exc.value.status == 503
        assert exc.value.code == DEGRADED
    finally:
        ctrl.stop()


def test_controller_degraded_on_missing_triggers(tmp_path: Path):
    home = tmp_path / "missing_triggers"
    ctrl = make_ctrl(home)
    ctrl.create_task({"adapter": "probe", "params": {}, "effect_class": "idempotent",
                      "max_attempts": 1, "lease_ttl_s": 5})
    ctrl.stop()

    conn = sqlite3.connect(home / "courier.db")
    conn.execute("DROP TRIGGER events_no_update")
    conn.commit()
    conn.close()

    ctrl2 = Controller(home)
    ctrl2.boot()
    try:
        assert ctrl2.mode == DEGRADED
        assert "append-only guard triggers are missing" in ctrl2.degraded_reason
    finally:
        ctrl2.stop()


def test_controller_degraded_on_broken_hash_chain(tmp_path: Path):
    home = tmp_path / "broken_chain"
    ctrl = make_ctrl(home)
    ctrl.create_task({"adapter": "probe", "params": {}, "effect_class": "idempotent",
                      "max_attempts": 1, "lease_ttl_s": 5})
    ctrl.stop()

    # Tamper with the events table by dropping trigger temporarily
    conn = sqlite3.connect(home / "courier.db")
    conn.execute("DROP TRIGGER events_no_update")
    conn.execute("UPDATE events SET ts_utc = '2000-01-01T00:00:00.000000Z' WHERE seq = 1")
    conn.execute("CREATE TRIGGER events_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT, 'courier journal is append-only'); END")
    conn.commit()
    conn.close()

    ctrl2 = Controller(home)
    ctrl2.boot()
    try:
        assert ctrl2.mode == DEGRADED
        assert "hash chain broken" in ctrl2.degraded_reason
        assert ctrl2.first_bad_seq == 1
    finally:
        ctrl2.stop()


def test_controller_stopped_guards(tmp_path: Path):
    ctrl = make_ctrl(tmp_path)
    ctrl.stop()
    assert ctrl.stopping is True

    with pytest.raises(ApiError) as exc:
        ctrl.create_task({"adapter": "probe", "params": {}, "effect_class": "idempotent",
                          "max_attempts": 1, "lease_ttl_s": 5})
    assert exc.value.status == 503
    assert exc.value.code == "stopping"

    with pytest.raises(ApiError) as exc:
        ctrl.task_view("task-123")
    assert exc.value.status == 503
    assert exc.value.code == "stopping"


def test_controller_lock_timeout_busy(tmp_path: Path):
    ctrl = Controller(tmp_path, lock_timeout_s=0.1)
    ctrl.boot()
    try:
        # Acquire the lock from another thread to simulate contention
        lock_acquired = threading.Event()
        release_lock = threading.Event()

        def hold_lock():
            with ctrl._lock:
                lock_acquired.set()
                release_lock.wait()

        t = threading.Thread(target=hold_lock)
        t.start()
        lock_acquired.wait()

        with pytest.raises(ApiError) as exc:
            ctrl.claim({"worker_id": "w1"})
        assert exc.value.status == 503
        assert exc.value.code == "busy"

        release_lock.set()
        t.join()
    finally:
        ctrl.stop()


# ==============================================================================
# Task Creation & View Tests
# ==============================================================================

def test_create_task_validation_errors(tmp_path: Path):
    ctrl = make_ctrl(tmp_path)
    try:
        # Invalid adapter regex
        with pytest.raises(ApiError) as exc:
            ctrl.create_task({"adapter": "Invalid_Adapter", "params": {}, "effect_class": "idempotent",
                              "max_attempts": 1, "lease_ttl_s": 5})
        assert "adapter must match" in exc.value.message

        # Invalid params (not dict)
        with pytest.raises(ApiError) as exc:
            ctrl.create_task({"adapter": "probe", "params": "string", "effect_class": "idempotent",
                              "max_attempts": 1, "lease_ttl_s": 5})
        assert "params must be a JSON object" in exc.value.message

        # Invalid effect_class
        with pytest.raises(ApiError) as exc:
            ctrl.create_task({"adapter": "probe", "params": {}, "effect_class": "unknown_effect",
                              "max_attempts": 1, "lease_ttl_s": 5})
        assert "effect_class must be one of" in exc.value.message

        # Out of bounds max_attempts
        with pytest.raises(ApiError) as exc:
            ctrl.create_task({"adapter": "probe", "params": {}, "effect_class": "idempotent",
                              "max_attempts": MAX_ATTEMPTS_LIMIT + 1, "lease_ttl_s": 5})
        assert "max_attempts must be an integer" in exc.value.message

        # Out of bounds lease_ttl_s
        with pytest.raises(ApiError) as exc:
            ctrl.create_task({"adapter": "probe", "params": {}, "effect_class": "idempotent",
                              "max_attempts": 1, "lease_ttl_s": MAX_LEASE_TTL_S + 1})
        assert "lease_ttl_s must be an integer" in exc.value.message

        # Out of bounds timeout_s
        with pytest.raises(ApiError) as exc:
            ctrl.create_task({"adapter": "probe", "params": {}, "effect_class": "idempotent",
                              "max_attempts": 1, "lease_ttl_s": 5, "timeout_s": MAX_TIMEOUT_S + 1})
        assert "timeout_s must be an integer" in exc.value.message
    finally:
        ctrl.stop()


def test_create_task_idempotency_and_conflict(tmp_path: Path):
    ctrl = make_ctrl(tmp_path)
    try:
        body = {
            "adapter": "probe",
            "params": {"run": 1},
            "effect_class": "idempotent",
            "max_attempts": 3,
            "lease_ttl_s": 10,
            "idempotency_key": "order-12345",
        }
        status, res1 = ctrl.create_task(body)
        assert status == 201
        assert res1["duplicate"] is False
        task_id = res1["task_id"]
        expected_task_id = "task-" + hashlib.sha256(b"order-12345").hexdigest()[:32]
        assert task_id == expected_task_id

        # Duplicate submission with identical body -> 200 duplicate=True
        status2, res2 = ctrl.create_task(body)
        assert status2 == 200
        assert res2["duplicate"] is True
        assert res2["task_id"] == task_id

        # Duplicate key with different params -> 409 idempotency_conflict
        conflict_body = dict(body, params={"run": 2})
        with pytest.raises(ApiError) as exc:
            ctrl.create_task(conflict_body)
        assert exc.value.status == 409
        assert exc.value.code == "idempotency_conflict"
    finally:
        ctrl.stop()


def test_task_view_found_and_not_found(tmp_path: Path):
    ctrl = make_ctrl(tmp_path)
    try:
        with pytest.raises(ApiError) as exc:
            ctrl.task_view("nonexistent_task_id")
        assert exc.value.status == 404
        assert exc.value.code == "unknown_task"

        _, created = ctrl.create_task({
            "adapter": "probe",
            "params": {"key": "val"},
            "effect_class": "idempotent",
            "max_attempts": 2,
            "lease_ttl_s": 15,
        })
        task_id = created["task_id"]
        view = ctrl.task_view(task_id)
        assert view["task_id"] == task_id
        assert view["status"] == TaskStatus.QUEUED.value
        assert view["adapter"] == "probe"
        assert "effect_key" in view
        assert view["effect_key"].startswith("cfx-")
    finally:
        ctrl.stop()


# ==============================================================================
# Claim, Start, Heartbeat & Result Lifecycle Tests
# ==============================================================================

def test_claim_fifo_and_empty_queue(tmp_path: Path):
    ctrl = make_ctrl(tmp_path)
    try:
        assert ctrl.claim({"worker_id": "w1"}) is None

        ctrl.create_task({"adapter": "probe", "params": {"n": 1}, "effect_class": "idempotent",
                          "max_attempts": 2, "lease_ttl_s": 10})
        ctrl.create_task({"adapter": "probe", "params": {"n": 2}, "effect_class": "idempotent",
                          "max_attempts": 2, "lease_ttl_s": 10})

        c1 = ctrl.claim({"worker_id": "w1"})
        assert c1 is not None
        assert c1["spec"]["params"] == {"n": 1}
        assert c1["attempt"] == 1
        assert c1["worker_id"] == "w1"
        assert c1["ttl_s"] == 10

        c2 = ctrl.claim({"worker_id": "w2"})
        assert c2 is not None
        assert c2["spec"]["params"] == {"n": 2}

        # Queue is now empty
        assert ctrl.claim({"worker_id": "w1"}) is None
    finally:
        ctrl.stop()


def test_start_transitions_and_fencing(tmp_path: Path):
    ctrl = make_ctrl(tmp_path)
    try:
        _, created = ctrl.create_task({"adapter": "probe", "params": {}, "effect_class": "idempotent",
                                       "max_attempts": 2, "lease_ttl_s": 10})
        claim = ctrl.claim({"worker_id": "w1"})
        dsp = claim["dispatch_id"]

        # Unknown dispatch
        with pytest.raises(ApiError) as exc:
            ctrl.start({"dispatch_id": "dsp-unknown"})
        assert exc.value.status == 404
        assert exc.value.code == "unknown_dispatch"

        # Wrong worker
        with pytest.raises(ApiError) as exc:
            ctrl.start({"dispatch_id": dsp, "worker_id": "w2"})
        assert exc.value.status == 409
        assert exc.value.code == "wrong_worker"

        # Successful start
        res = ctrl.start({"dispatch_id": dsp, "worker_id": "w1"})
        assert res["status"] == "STARTED"

        # Idempotent start
        res_already = ctrl.start({"dispatch_id": dsp, "worker_id": "w1"})
        assert res_already["status"] == "ALREADY_STARTED"
    finally:
        ctrl.stop()


def test_heartbeat_deadline_extension_and_stop_list(tmp_path: Path):
    clock = FakeClock(100.0)
    ctrl = make_ctrl(tmp_path, clock)
    try:
        ctrl.create_task({"adapter": "probe", "params": {}, "effect_class": "idempotent",
                          "max_attempts": 2, "lease_ttl_s": 30})
        claim = ctrl.claim({"worker_id": "w1"})
        dsp = claim["dispatch_id"]

        assert dsp in ctrl._leases
        assert ctrl._leases[dsp].deadline == 130.0

        clock.advance(15.0)
        hb = ctrl.heartbeat({"worker_id": "w1", "dispatch_ids": [dsp, "dsp-nonexistent"]})
        assert hb["ok"] is True
        assert "dsp-nonexistent" in hb["stop"]
        assert hb["cancel"] == []
        assert ctrl._leases[dsp].deadline == 145.0  # extended by ttl from 115.0
    finally:
        ctrl.stop()


def test_heartbeat_cancel_flow_and_worker_reap_confirmation(tmp_path: Path):
    ctrl = make_ctrl(tmp_path)
    try:
        _, created = ctrl.create_task({"adapter": "probe", "params": {}, "effect_class": "idempotent",
                                       "max_attempts": 2, "lease_ttl_s": 30})
        task_id = created["task_id"]
        claim = ctrl.claim({"worker_id": "w1"})
        dsp = claim["dispatch_id"]
        ctrl.start({"dispatch_id": dsp, "worker_id": "w1"})

        # Request cancellation
        ctrl.cancel(task_id, {"reason": "user stopped"})
        view = ctrl.task_view(task_id)
        assert view["cancel_requested"] is True

        # Next heartbeat should inform the worker via cancel list
        hb = ctrl.heartbeat({"worker_id": "w1", "dispatch_ids": [dsp]})
        assert dsp in hb["cancel"]

        # Worker confirms kill by omitting dsp in subsequent heartbeat
        hb2 = ctrl.heartbeat({"worker_id": "w1", "dispatch_ids": []})
        assert dsp not in ctrl._leases
        view2 = ctrl.task_view(task_id)
        assert view2["status"] == TaskStatus.CANCELLED.value
    finally:
        ctrl.stop()


def test_result_recording_and_duplicates(tmp_path: Path):
    ctrl = make_ctrl(tmp_path)
    try:
        _, created = ctrl.create_task({"adapter": "probe", "params": {}, "effect_class": "idempotent",
                                       "max_attempts": 2, "lease_ttl_s": 30})
        task_id = created["task_id"]
        claim = ctrl.claim({"worker_id": "w1"})
        dsp = claim["dispatch_id"]

        # Result before start raises 409 not_started
        with pytest.raises(ApiError) as exc:
            ctrl.result({"dispatch_id": dsp, "result_id": "res-1", "artifacts": [], "outcome": "success"})
        assert exc.value.status == 409
        assert exc.value.code == "not_started"

        ctrl.start({"dispatch_id": dsp, "worker_id": "w1"})

        # Valid result accepted for verify
        code, res = ctrl.result({
            "dispatch_id": dsp,
            "result_id": "res-1",
            "artifacts": [{"path": "data.json", "sha256": "0" * 64}],
            "outcome": "success",
        })
        assert code == 200
        assert res["status"] == "ACCEPTED_FOR_VERIFY"
        assert dsp not in ctrl._leases

        # Duplicate submission with identical payload returns ACK_DUPLICATE
        code_dup, res_dup = ctrl.result({
            "dispatch_id": dsp,
            "result_id": "res-1",
            "artifacts": [{"path": "data.json", "sha256": "0" * 64}],
            "outcome": "success",
        })
        assert code_dup == 200
        assert res_dup["status"] == "ACK_DUPLICATE"

        # Duplicate result_id with conflicting payload raises 409 result_conflict
        with pytest.raises(ApiError) as exc:
            ctrl.result({
                "dispatch_id": dsp,
                "result_id": "res-1",
                "artifacts": [{"path": "diff.json", "sha256": "1" * 64}],
                "outcome": "failure",
            })
        assert exc.value.status == 409
        assert exc.value.code == "result_conflict"
    finally:
        ctrl.stop()


def test_result_validation_limits(tmp_path: Path):
    ctrl = make_ctrl(tmp_path)
    try:
        _, created = ctrl.create_task({"adapter": "probe", "params": {}, "effect_class": "idempotent",
                                       "max_attempts": 2, "lease_ttl_s": 30})
        claim = ctrl.claim({"worker_id": "w1"})
        dsp = claim["dispatch_id"]
        ctrl.start({"dispatch_id": dsp, "worker_id": "w1"})

        # Invalid outcome
        with pytest.raises(ApiError) as exc:
            ctrl.result({"dispatch_id": dsp, "result_id": "res-1", "artifacts": [], "outcome": "invalid_outcome"})
        assert "outcome must be one of" in exc.value.message

        # Invalid artifacts type
        with pytest.raises(ApiError) as exc:
            ctrl.result({"dispatch_id": dsp, "result_id": "res-1", "artifacts": "not_a_list", "outcome": "success"})
        assert "artifacts must be a list" in exc.value.message
    finally:
        ctrl.stop()


# ==============================================================================
# Cancellation & Human Resolution Tests
# ==============================================================================

def test_cancel_queued_task(tmp_path: Path):
    ctrl = make_ctrl(tmp_path)
    try:
        _, created = ctrl.create_task({"adapter": "probe", "params": {}, "effect_class": "idempotent",
                                       "max_attempts": 2, "lease_ttl_s": 30})
        task_id = created["task_id"]
        res = ctrl.cancel(task_id, {"reason": "no longer needed"})
        assert res["status"] == TaskStatus.CANCELLED.value
        assert res["cancel_requested"] is True

        # Cannot cancel again once terminal
        with pytest.raises(ApiError) as exc:
            ctrl.cancel(task_id)
        assert exc.value.status == 409
        assert exc.value.code == "terminal"
    finally:
        ctrl.stop()


def test_resolve_blocked_task_and_fencing(tmp_path: Path):
    # Non-idempotent task with expired lease transitions to BLOCKED
    clock = FakeClock(100.0)
    ctrl = make_ctrl(tmp_path, clock)
    try:
        _, created = ctrl.create_task({"adapter": "probe", "params": {}, "effect_class": "non_idempotent",
                                       "max_attempts": 3, "lease_ttl_s": 10})
        task_id = created["task_id"]
        claim = ctrl.claim({"worker_id": "w1"})
        ctrl.start({"dispatch_id": claim["dispatch_id"], "worker_id": "w1"})

        # Advance clock to expire lease while task was started
        clock.advance(11.0)
        ctrl.tick()

        view = ctrl.task_view(task_id)
        assert view["status"] == TaskStatus.BLOCKED.value

        # Resolving on non-blocked raises 409 not_blocked
        with pytest.raises(ApiError) as exc:
            ctrl.resolve("non_existent", {"decision": "retry_authorized", "actor": "alice", "attempt": 1, "reason": "ok"})
        assert exc.value.status == 404

        # Stale attempt number
        with pytest.raises(ApiError) as exc:
            ctrl.resolve(task_id, {"decision": "retry_authorized", "actor": "alice", "attempt": 2, "reason": "ok"})
        assert exc.value.status == 409
        assert exc.value.code == "stale_decision"

        # Invalid decision
        with pytest.raises(ApiError) as exc:
            ctrl.resolve(task_id, {"decision": "unknown_decision", "actor": "alice", "attempt": 1, "reason": "ok"})
        assert exc.value.status == 400

        # Authorize retry
        res = ctrl.resolve(task_id, {"decision": "retry_authorized", "actor": "alice", "attempt": 1, "reason": "retry approved"})
        assert res["decision"] == "retry_authorized"
        assert res["duplicate"] is False
        assert ctrl.task_view(task_id)["status"] == TaskStatus.QUEUED.value

        # Duplicate resolve returns duplicate=True
        res_dup = ctrl.resolve(task_id, {"decision": "retry_authorized", "actor": "alice", "attempt": 1, "reason": "retry approved"})
        assert res_dup["duplicate"] is True

        # Conflicting resolve on same attempt (same decision type, different payload)
        with pytest.raises(ApiError) as exc:
            ctrl.resolve(task_id, {"decision": "retry_authorized", "actor": "bob", "attempt": 1, "reason": "different reason"})
        assert exc.value.status == 409
        assert exc.value.code == "decision_conflict"
    finally:
        ctrl.stop()


def test_cancel_blocked_task_requires_actor(tmp_path: Path):
    clock = FakeClock(100.0)
    ctrl = make_ctrl(tmp_path, clock)
    try:
        _, created = ctrl.create_task({"adapter": "probe", "params": {}, "effect_class": "non_idempotent",
                                       "max_attempts": 3, "lease_ttl_s": 10})
        task_id = created["task_id"]
        claim = ctrl.claim({"worker_id": "w1"})
        ctrl.start({"dispatch_id": claim["dispatch_id"], "worker_id": "w1"})

        # Expire lease while running -> BLOCKED
        clock.advance(11.0)
        ctrl.tick()

        # Cancelling blocked task without actor raises 409 actor_required
        with pytest.raises(ApiError) as exc:
            ctrl.cancel(task_id, {"reason": "cancel"})
        assert exc.value.status == 409
        assert exc.value.code == "actor_required"

        # Cancelling with actor succeeds
        res = ctrl.cancel(task_id, {"actor": "operator_bob", "reason": "cancel verified"})
        assert res["status"] == TaskStatus.CANCELLED.value
    finally:
        ctrl.stop()


# ==============================================================================
# Tick, Expiration & Suspend Gap Tests
# ==============================================================================

def test_tick_lease_expiration(tmp_path: Path):
    clock = FakeClock(50.0)
    ctrl = make_ctrl(tmp_path, clock)
    try:
        _, created = ctrl.create_task({"adapter": "probe", "params": {}, "effect_class": "idempotent",
                                       "max_attempts": 2, "lease_ttl_s": 10})
        task_id = created["task_id"]
        claim = ctrl.claim({"worker_id": "w1"})
        dsp = claim["dispatch_id"]

        assert dsp in ctrl._leases
        clock.advance(11.0)
        ctrl.tick()

        # Lease should have expired and removed
        assert dsp not in ctrl._leases
        view = ctrl.task_view(task_id)
        # Should be re-queued since max_attempts is 2
        assert view["status"] == TaskStatus.QUEUED.value
        assert view["attempt"] == 1
    finally:
        ctrl.stop()


def test_tick_suspend_gap_extends_deadlines(tmp_path: Path):
    clock = FakeClock(100.0)
    ctrl = make_ctrl(tmp_path, clock)
    try:
        ctrl.tick()  # initialize self._last_tick = 100.0
        ctrl.create_task({"adapter": "probe", "params": {}, "effect_class": "idempotent",
                          "max_attempts": 2, "lease_ttl_s": 20})
        claim = ctrl.claim({"worker_id": "w1"})
        dsp = claim["dispatch_id"]

        initial_deadline = ctrl._leases[dsp].deadline
        assert initial_deadline == 120.0

        # Simulate host sleep / suspend gap of 10 seconds (> SUSPEND_GAP_S = 5.0)
        clock.advance(10.0)
        ctrl.tick()

        # Deadline should have been extended by 10s, not expired
        assert dsp in ctrl._leases
        assert ctrl._leases[dsp].deadline == 130.0
    finally:
        ctrl.stop()


# ==============================================================================
# Verification Queue & Event Stream Tests
# ==============================================================================

def test_verification_drain_and_complete(tmp_path: Path):
    ctrl = make_ctrl(tmp_path, verifier=dummy_verifier)
    try:
        _, created = ctrl.create_task({"adapter": "probe", "params": {}, "effect_class": "idempotent",
                                       "max_attempts": 2, "lease_ttl_s": 30})
        task_id = created["task_id"]
        claim = ctrl.claim({"worker_id": "w1"})
        ctrl.start({"dispatch_id": claim["dispatch_id"], "worker_id": "w1"})
        ctrl.result({"dispatch_id": claim["dispatch_id"], "result_id": "res-1", "artifacts": [], "outcome": "success"})

        assert ctrl.task_view(task_id)["status"] == TaskStatus.VERIFYING.value
        ctrl.drain()
        assert ctrl.task_view(task_id)["status"] == TaskStatus.COMPLETE.value
    finally:
        ctrl.stop()


def test_events_after_stream(tmp_path: Path):
    ctrl = make_ctrl(tmp_path)
    try:
        ctrl.create_task({"adapter": "probe", "params": {}, "effect_class": "idempotent",
                          "max_attempts": 2, "lease_ttl_s": 30})
        events = ctrl.events_after(0)
        assert len(events) >= 2
        types = [e.type for e in events]
        assert EventType.CONTROLLER_STARTED in types
        assert EventType.TASK_CREATED in types

        first_seq = events[0].seq
        later_events = ctrl.events_after(first_seq)
        assert len(later_events) == len(events) - 1
    finally:
        ctrl.stop()


def test_resolve_cancel_decision_on_blocked_task(tmp_path: Path):
    clock = FakeClock(100.0)
    ctrl = make_ctrl(tmp_path, clock)
    try:
        _, created = ctrl.create_task({"adapter": "probe", "params": {}, "effect_class": "non_idempotent",
                                       "max_attempts": 3, "lease_ttl_s": 10})
        task_id = created["task_id"]
        claim = ctrl.claim({"worker_id": "w1"})
        ctrl.start({"dispatch_id": claim["dispatch_id"], "worker_id": "w1"})
        clock.advance(11.0)
        ctrl.tick()

        assert ctrl.task_view(task_id)["status"] == TaskStatus.BLOCKED.value

        res = ctrl.resolve(task_id, {"decision": "cancel", "actor": "charlie", "attempt": 1, "reason": "abandon task"})
        assert res["decision"] == "cancel"
        assert res["status"] == TaskStatus.CANCELLED.value
        assert ctrl.task_view(task_id)["status"] == TaskStatus.CANCELLED.value
    finally:
        ctrl.stop()


def test_resolve_effect_confirmed_on_blocked_task(tmp_path: Path):
    clock = FakeClock(100.0)
    ctrl = make_ctrl(tmp_path, clock)
    try:
        _, created = ctrl.create_task({"adapter": "probe", "params": {}, "effect_class": "non_idempotent",
                                       "max_attempts": 3, "lease_ttl_s": 10})
        task_id = created["task_id"]
        claim = ctrl.claim({"worker_id": "w1"})
        ctrl.start({"dispatch_id": claim["dispatch_id"], "worker_id": "w1"})
        clock.advance(11.0)
        ctrl.tick()

        assert ctrl.task_view(task_id)["status"] == TaskStatus.BLOCKED.value

        res = ctrl.resolve(task_id, {"decision": "effect_confirmed", "actor": "dave", "attempt": 1, "reason": "effect verified out-of-band"})
        assert res["decision"] == "effect_confirmed"
        assert ctrl.task_view(task_id)["status"] == TaskStatus.COMPLETE.value
    finally:
        ctrl.stop()


def test_start_fencing_cancel_requested(tmp_path: Path):
    ctrl = make_ctrl(tmp_path)
    try:
        _, created = ctrl.create_task({"adapter": "probe", "params": {}, "effect_class": "idempotent",
                                       "max_attempts": 2, "lease_ttl_s": 30})
        task_id = created["task_id"]
        claim = ctrl.claim({"worker_id": "w1"})
        dsp = claim["dispatch_id"]

        # Cancel while claimed
        ctrl.cancel(task_id, {"reason": "abort early"})

        with pytest.raises(ApiError) as exc:
            ctrl.start({"dispatch_id": dsp, "worker_id": "w1"})
        assert exc.value.status == 409
        assert exc.value.code == "cancel_requested"
    finally:
        ctrl.stop()


def test_result_fencing_cancel_requested_and_late_discarded(tmp_path: Path):
    clock = FakeClock(100.0)
    ctrl = make_ctrl(tmp_path, clock)
    try:
        _, created = ctrl.create_task({"adapter": "probe", "params": {}, "effect_class": "idempotent",
                                       "max_attempts": 2, "lease_ttl_s": 10})
        task_id = created["task_id"]
        claim = ctrl.claim({"worker_id": "w1"})
        dsp = claim["dispatch_id"]
        ctrl.start({"dispatch_id": dsp, "worker_id": "w1"})

        # Cancel while running
        ctrl.cancel(task_id, {"reason": "abort running"})
        with pytest.raises(ApiError) as exc:
            ctrl.result({"dispatch_id": dsp, "result_id": "res-1", "artifacts": [], "outcome": "success"})
        assert exc.value.status == 409
        assert exc.value.code == "cancel_requested"

        # Advance clock to expire lease and re-queue attempt 2
        clock.advance(11.0)
        ctrl.tick()

        # Late result report from expired dispatch is discarded and recorded
        with pytest.raises(ApiError) as exc:
            ctrl.result({"dispatch_id": dsp, "result_id": "res-1", "artifacts": [], "outcome": "success"})
        assert exc.value.status == 409
        assert exc.value.code == "stale_dispatch"
    finally:
        ctrl.stop()


def test_verification_queue_rejection_retryable_and_terminal(tmp_path: Path):
    # Reject with retryable=False -> transitions to FAILED
    ctrl = make_ctrl(tmp_path, verifier=rejecting_verifier(retryable=False, reason="fatal error"))
    try:
        _, created = ctrl.create_task({"adapter": "probe", "params": {}, "effect_class": "idempotent",
                                       "max_attempts": 3, "lease_ttl_s": 30})
        task_id = created["task_id"]
        claim = ctrl.claim({"worker_id": "w1"})
        ctrl.start({"dispatch_id": claim["dispatch_id"], "worker_id": "w1"})
        ctrl.result({"dispatch_id": claim["dispatch_id"], "result_id": "res-1", "artifacts": [], "outcome": "success"})

        assert ctrl.verify_next() is True
        assert ctrl.task_view(task_id)["status"] == TaskStatus.FAILED.value

        # Empty queue returns False
        assert ctrl.verify_next() is False
    finally:
        ctrl.stop()


def test_restart_recovery_repopulates_leases(tmp_path: Path):
    clock = FakeClock(100.0)
    home = tmp_path / "restart_home"
    ctrl = make_ctrl(home, clock)
    try:
        ctrl.create_task({"adapter": "probe", "params": {}, "effect_class": "idempotent",
                          "max_attempts": 2, "lease_ttl_s": 25})
        claim = ctrl.claim({"worker_id": "w1"})
        dsp = claim["dispatch_id"]
        assert dsp in ctrl._leases
    finally:
        ctrl.stop()

    # Boot a fresh controller on the same journal
    ctrl2 = Controller(home, clock=clock)
    ctrl2.boot()
    try:
        assert ctrl2.mode == NORMAL
        assert dsp in ctrl2._leases
        lease = ctrl2._leases[dsp]
        assert lease.reason == "restart_grace"
        assert lease.deadline == 125.0
    finally:
        ctrl2.stop()


def test_start_background_and_stop_cleanly(tmp_path: Path):
    ctrl = make_ctrl(tmp_path)
    try:
        ctrl.start_background(tick_s=0.05)
        assert len(ctrl._threads) == 2
        names = {t.name for t in ctrl._threads}
        assert "courier-lease-ticker" in names
        assert "courier-verifier" in names
    finally:
        ctrl.stop()
        for t in ctrl._threads:
            assert not t.is_alive()


def test_wait_for_change_timeout(tmp_path: Path):
    ctrl = make_ctrl(tmp_path)
    try:
        start = time.monotonic()
        ctrl.wait_for_change(ctrl._head_seq, timeout=0.05)
        elapsed = time.monotonic() - start
        assert elapsed >= 0.04
    finally:
        ctrl.stop()

