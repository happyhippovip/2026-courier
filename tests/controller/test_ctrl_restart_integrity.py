"""L2 controller: restart recovery (H) and journal corruption handling (L)."""

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from ctrl_helpers import FakeClock, Verifiers, accept_all, make_controller, result_body, task_body, types
from courier_core.controller import DEGRADED, NORMAL, ApiError
from courier_core.journal import Journal
from courier_core.projection import projection_hash
from courier_core.state_machine import TaskStatus


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def crash(ctl):
    """Simulate a hard kill: no CONTROLLER_STOPPED, journal just closed."""
    ctl._stopping.set()
    ctl.journal.close()


def pass_time(ctl, clock, seconds, step=0.25):
    elapsed = 0.0
    while elapsed < seconds:
        clock.advance(step)
        elapsed += step
        ctl.tick()


# ------------------------------------------------------------- H. restart
def test_restart_keeps_projection_and_logs_lifecycle(tmp_path):
    home = tmp_path / "home"
    ctl = make_controller(home)
    ctl.create_task(task_body())
    digest = projection_hash(ctl.journal.conn)
    ctl.stop()
    again = make_controller(home)
    try:
        assert again.mode == NORMAL and projection_hash(again.journal.conn) == digest
        system = [e.type.value for e in again.journal.events() if e.task_id is None]
        assert system == ["CONTROLLER_STARTED", "CONTROLLER_STOPPED", "CONTROLLER_STARTED"]
    finally:
        again.stop()


def test_live_worker_keeps_its_dispatch_across_restart(tmp_path):
    home, clock = tmp_path / "home", FakeClock()
    ctl = make_controller(home, clock=clock)
    _, body = ctl.create_task(task_body(lease_ttl_s=12))
    lease = ctl.claim({"worker_id": "w1"})
    ctl.start({"dispatch_id": lease["dispatch_id"]})
    crash(ctl)
    clock2 = FakeClock()
    ctl = make_controller(home, clock=clock2)
    try:
        for _ in range(12):  # worker heartbeats every 2s through the grace window and beyond
            pass_time(ctl, clock2, 2)
            assert ctl.heartbeat({"worker_id": "w1", "dispatch_ids": [lease["dispatch_id"]]})["stop"] == []
        ctl.result(result_body(lease["dispatch_id"]))
        ctl.drain()
        seq = types(ctl, body["task_id"])
        assert "LEASE_EXPIRED" not in seq and seq[-1] == "TASK_COMPLETE"
        assert len({e.dispatch_id for e in ctl.journal.events(task_id=body["task_id"]) if e.dispatch_id}) == 1
    finally:
        ctl.stop()


def test_vanished_worker_expires_with_restart_grace(tmp_path):
    home = tmp_path / "home"
    ctl = make_controller(home)
    _, body = ctl.create_task(task_body())
    lease = ctl.claim({"worker_id": "w1"})
    ctl.start({"dispatch_id": lease["dispatch_id"]})
    crash(ctl)
    clock = FakeClock()
    ctl = make_controller(home, clock=clock)
    try:
        assert ctl.health()["active_leases"] == 1
        pass_time(ctl, clock, 5.5)
        assert ctl.journal.task(body["task_id"]).status is TaskStatus.RUNNING
        pass_time(ctl, clock, 1)
        expired = [e for e in ctl.journal.events(task_id=body["task_id"]) if e.type.value == "LEASE_EXPIRED"]
        assert [e.payload["reason"] for e in expired] == ["restart_grace"]
        assert types(ctl, body["task_id"])[-1] == "TASK_BLOCKED"
        assert ctl.claim({"worker_id": "w2"}) is None
    finally:
        ctl.stop()


def test_restart_grace_blocks_uncertain_non_idempotent_work(tmp_path):
    home = tmp_path / "home"
    ctl = make_controller(home)
    _, body = ctl.create_task(task_body(effect_class="non_idempotent"))
    lease = ctl.claim({"worker_id": "w1"})
    ctl.start({"dispatch_id": lease["dispatch_id"]})
    crash(ctl)
    clock = FakeClock()
    ctl = make_controller(home, clock=clock)
    try:
        pass_time(ctl, clock, 7)
        assert types(ctl, body["task_id"])[-2:] == ["LEASE_EXPIRED", "TASK_BLOCKED"]
        assert ctl.claim({"worker_id": "w2"}) is None
    finally:
        ctl.stop()


def test_pending_verification_is_finished_after_restart(tmp_path):
    home = tmp_path / "home"
    ctl = make_controller(home)
    _, body = ctl.create_task(task_body())
    lease = ctl.claim({"worker_id": "w1"})
    ctl.start({"dispatch_id": lease["dispatch_id"]})
    ctl.result(result_body(lease["dispatch_id"]))  # crash before the verifier ran
    crash(ctl)
    verifier = Verifiers(probe=accept_all)
    ctl = make_controller(home, verifier=verifier)
    try:
        ctl.drain()
        assert types(ctl, body["task_id"])[-1] == "TASK_COMPLETE" and len(verifier.calls) == 1
    finally:
        ctl.stop()


def test_accepted_result_is_completed_after_restart(tmp_path):
    home = tmp_path / "home"
    ctl = make_controller(home)
    _, body = ctl.create_task(task_body())
    lease = ctl.claim({"worker_id": "w1"})
    ctl.start({"dispatch_id": lease["dispatch_id"]})
    ctl.result(result_body(lease["dispatch_id"]))
    from courier_core.events import Event, EventType
    ctl.journal.append(Event(type=EventType.RESULT_ACCEPTED, task_id=body["task_id"], attempt=1,
                             dispatch_id=lease["dispatch_id"], result_id="r1"))
    crash(ctl)  # crashed between RESULT_ACCEPTED and TASK_COMPLETE
    ctl = make_controller(home)
    try:
        assert types(ctl, body["task_id"])[-2:] == ["RESULT_ACCEPTED", "TASK_COMPLETE"]
    finally:
        ctl.stop()


def test_pending_retry_decision_is_taken_after_restart(tmp_path):
    home = tmp_path / "home"
    ctl = make_controller(home)
    _, body = ctl.create_task(task_body())
    lease = ctl.claim({"worker_id": "w1"})
    from courier_core.events import Event, EventType
    ctl.journal.append(Event(type=EventType.LEASE_EXPIRED, task_id=body["task_id"], attempt=1,
                             dispatch_id=lease["dispatch_id"], worker_id="w1", payload={"reason": "ttl"}))
    crash(ctl)  # crashed before the retry decision was journaled
    ctl = make_controller(home)
    try:
        assert types(ctl, body["task_id"])[-1] == "TASK_RETRY_SCHEDULED"
        assert ctl.claim({"worker_id": "w2"})["attempt"] == 2
    finally:
        ctl.stop()


# ------------------------------------------------------ L. corruption
def _prepared_home(tmp_path):
    home = tmp_path / "home"
    ctl = make_controller(home)
    ctl.create_task(task_body())
    lease = ctl.claim({"worker_id": "w1"})
    ctl.start({"dispatch_id": lease["dispatch_id"]})
    ctl.stop()
    return home


def _raw(home):
    return sqlite3.connect(str(home / "courier.db"), isolation_level=None)


def _assert_degraded_and_untouched(home, digest_before, first_bad_seq=None):
    ctl = make_controller(home)
    try:
        health = ctl.health()
        assert health["mode"] == DEGRADED and health["reason"]
        if first_bad_seq is not None:
            assert health["first_bad_seq"] == first_bad_seq
        for call, arg in ((ctl.create_task, task_body()), (ctl.claim, {"worker_id": "w"}),
                          (ctl.start, {"dispatch_id": "d"}), (ctl.heartbeat, {"worker_id": "w", "dispatch_ids": []}),
                          (ctl.result, result_body("d")), (ctl.cancel, "t")):
            with pytest.raises(ApiError) as info:
                call(arg)
            assert info.value.status == 503 and info.value.code == "degraded_readonly"
        ctl.tick()
        ctl.drain()
    finally:
        ctl.stop()
    assert file_digest(home / "courier.db") == digest_before, "degraded boot must not modify the journal file"


def test_tampered_payload_starts_degraded_with_first_bad_seq(tmp_path):
    home = _prepared_home(tmp_path)
    conn = _raw(home)
    for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall():
        conn.execute(f'DROP TRIGGER "{name}"')
    body = json.loads(conn.execute("SELECT payload FROM events WHERE seq = 3").fetchone()[0])
    body["golden_tampered"] = True
    conn.execute("UPDATE events SET payload = ? WHERE seq = 3", (json.dumps(body),))
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    _assert_degraded_and_untouched(home, file_digest(home / "courier.db"), first_bad_seq=3)


def test_missing_append_only_guard_starts_degraded(tmp_path):
    home = _prepared_home(tmp_path)
    conn = _raw(home)
    conn.execute("DROP TRIGGER events_no_delete")
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    _assert_degraded_and_untouched(home, file_digest(home / "courier.db"))


def test_edited_projection_starts_degraded(tmp_path):
    home = _prepared_home(tmp_path)
    conn = _raw(home)
    conn.execute("UPDATE tasks SET status = 'COMPLETE'")
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    _assert_degraded_and_untouched(home, file_digest(home / "courier.db"))


def test_unreadable_database_starts_degraded_and_is_preserved(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / "courier.db").write_bytes(b"this is not a sqlite database" * 100)
    _assert_degraded_and_untouched(home, file_digest(home / "courier.db"))


def test_degraded_controller_still_serves_reads(tmp_path):
    home = _prepared_home(tmp_path)
    conn = _raw(home)
    conn.execute("DROP TRIGGER events_no_update")
    conn.execute("UPDATE events SET ts_utc = '2000-01-01T00:00:00.000000Z' WHERE seq = 2")
    conn.close()
    ctl = make_controller(home)
    try:
        assert ctl.mode == DEGRADED and ctl.first_bad_seq == 2
        assert len(ctl.events_after(0)) >= 4
    finally:
        ctl.stop()
    with Journal(home / "courier.db", readonly=True) as inspector:
        assert not inspector.verify_chain().ok
