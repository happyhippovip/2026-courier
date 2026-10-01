"""L2 adversarial hardening: timing boundaries, SSE across restarts, page corruption, shutdown races."""

import hashlib
import threading
import time

import pytest
import requests

from ctrl_helpers import (
    FakeClock, LiveService, Verifiers, make_controller, run_attempt, task_body, types,
)
from courier_core import serve
from courier_core.controller import DEGRADED, ApiError
from courier_core.verification import Verdict


def pass_time(ctl, clock, seconds, step=0.25):
    elapsed = 0.0
    while elapsed < seconds - 1e-9:
        delta = min(step, seconds - elapsed)
        clock.advance(delta)
        elapsed += delta
        ctl.tick()


def api_error(fn, *args):
    with pytest.raises(ApiError) as info:
        fn(*args)
    return info.value


# ------------------------------------------------------------ lease timing
def test_expiry_is_exactly_ttl_after_the_last_heartbeat(tmp_path):
    clock = FakeClock()
    ctl = make_controller(tmp_path / "home", clock=clock)
    try:
        _, body = ctl.create_task(task_body(lease_ttl_s=6))
        lease = ctl.claim({"worker_id": "w1"})
        pass_time(ctl, clock, 5.75)
        ctl.heartbeat({"worker_id": "w1", "dispatch_ids": [lease["dispatch_id"]]})  # just before the boundary
        pass_time(ctl, clock, 5.75)
        assert "LEASE_EXPIRED" not in types(ctl, body["task_id"])
        pass_time(ctl, clock, 0.5)
        assert types(ctl, body["task_id"]).count("LEASE_EXPIRED") == 1
    finally:
        ctl.stop()


def test_heartbeat_after_expiry_cannot_resurrect_the_dispatch(tmp_path):
    clock = FakeClock()
    ctl = make_controller(tmp_path / "home", clock=clock)
    try:
        _, body = ctl.create_task(task_body())
        lease = ctl.claim({"worker_id": "w1"})
        ctl.start({"dispatch_id": lease["dispatch_id"]})
        pass_time(ctl, clock, 7)
        answer = ctl.heartbeat({"worker_id": "w1", "dispatch_ids": [lease["dispatch_id"]]})
        assert answer["stop"] == [lease["dispatch_id"]]
        new = ctl.claim({"worker_id": "w2"})
        assert new["attempt"] == 2 and new["dispatch_id"] != lease["dispatch_id"]
    finally:
        ctl.stop()


@pytest.mark.parametrize("round_", range(5))
def test_restart_never_produces_a_false_expiry_for_a_beating_worker(tmp_path, round_):
    home = tmp_path / "home"
    ctl = make_controller(home)
    _, body = ctl.create_task(task_body(lease_ttl_s=3))
    lease = ctl.claim({"worker_id": "w1"})
    ctl.start({"dispatch_id": lease["dispatch_id"]})
    ctl._stopping.set()
    ctl.journal.close()
    clock = FakeClock()
    ctl = make_controller(home, clock=clock)
    try:
        for _ in range(20):
            pass_time(ctl, clock, 1.0)  # heartbeat every ttl/3 = 1 s
            ctl.heartbeat({"worker_id": "w1", "dispatch_ids": [lease["dispatch_id"]]})
        assert "LEASE_EXPIRED" not in types(ctl, body["task_id"])
    finally:
        ctl.stop()


# --------------------------------------------------------- invalid steps
def test_invalid_transitions_over_the_api_change_nothing(tmp_path):
    ctl = make_controller(tmp_path / "home")
    try:
        _, body = ctl.create_task(task_body(max_attempts=1))
        lease = run_attempt(ctl)
        ctl.drain()
        head = ctl.journal.head()
        assert api_error(ctl.start, {"dispatch_id": lease["dispatch_id"]}).status == 409
        assert api_error(ctl.cancel, body["task_id"]).status == 409
        assert ctl.claim({"worker_id": "w9"}) is None
        assert ctl.heartbeat({"worker_id": "w1", "dispatch_ids": [lease["dispatch_id"]]})["stop"] == \
            [lease["dispatch_id"]]
        assert ctl.journal.head() == head
    finally:
        ctl.stop()


# ------------------------------------------------------------- shutdown
def test_stop_during_a_slow_verification_writes_nothing_after_close(tmp_path):
    entered, release = threading.Event(), threading.Event()

    def slow(task, result, home):
        entered.set()
        release.wait(5)
        return Verdict(True, "ok")

    home = tmp_path / "home"
    ctl = make_controller(home, verifier=Verifiers(probe=slow))
    _, body = ctl.create_task(task_body())
    run_attempt(ctl)
    worker = threading.Thread(target=ctl.verify_next)
    worker.start()
    assert entered.wait(5)
    ctl.stop(join_timeout_s=0.1)
    release.set()
    worker.join(5)
    again = make_controller(home)
    try:
        assert again.journal.task(body["task_id"]).status.value == "VERIFYING"
        again.drain()  # re-verified after the restart
        assert types(again, body["task_id"])[-1] == "TASK_COMPLETE"
    finally:
        again.stop()


def test_requests_during_shutdown_get_503(tmp_path):
    ctl = make_controller(tmp_path / "home")
    ctl._stopping.set()
    try:
        for call, arg in ((ctl.create_task, task_body()), (ctl.claim, {"worker_id": "w"}),
                          (ctl.task_view, "t")):
            assert api_error(call, arg).code == "stopping"
    finally:
        ctl.stop()


# ------------------------------------------------------------------- SSE
def _ids(service, last, until, timeout=10):
    out = []
    deadline = time.monotonic() + timeout
    with service.session.get(service.base + "/v1/events", headers={"Last-Event-ID": str(last)}, stream=True,
                             timeout=(5, 2)) as response:
        try:
            for line in response.iter_lines(decode_unicode=True):
                if line.startswith("id:"):
                    out.append(int(line[3:]))
                    if out[-1] >= until:
                        break
                if time.monotonic() > deadline:
                    break
        except requests.exceptions.ConnectionError:
            pass
    return out


def test_sse_resume_across_a_controller_restart_has_no_gaps_or_duplicates(tmp_path):
    home = tmp_path / "home"
    first = LiveService(home)
    first.post("/v1/tasks", task_body())
    seen = _ids(first, 0, first.controller.health()["head_seq"])
    first.stop()  # CONTROLLER_STOPPED appended
    second = LiveService(home)
    try:
        second.post("/v1/tasks", task_body())
        head = second.controller.health()["head_seq"]
        resumed = _ids(second, seen[-1], head)
        assert resumed == list(range(seen[-1] + 1, head + 1))
        again = _ids(second, seen[-1], head)  # a duplicate reconnect sees the same immutable events
        assert again == resumed
        assert sorted(set(seen + resumed)) == list(range(1, head + 1))
    finally:
        second.stop()


def test_empty_stream_sends_keepalives_and_stays_bounded(tmp_path, monkeypatch):
    monkeypatch.setattr(serve, "SSE_KEEPALIVE_S", 1.0)
    service = LiveService(tmp_path / "home")
    try:
        head = service.controller.health()["head_seq"]
        with service.session.get(service.base + "/v1/events", headers={"Last-Event-ID": str(head)},
                                 stream=True, timeout=(5, 5)) as response:
            lines = []
            for line in response.iter_lines(decode_unicode=True):
                lines.append(line)
                if line.startswith(": keepalive"):
                    break
        assert ": keepalive" in lines and not any(line.startswith("id:") for line in lines)
    finally:
        service.stop()


def test_event_streams_are_capped(tmp_path, monkeypatch):
    monkeypatch.setattr(serve, "MAX_EVENT_STREAMS", 2)
    service = LiveService(tmp_path / "home")
    opened = []
    try:
        for _ in range(2):
            opened.append(service.session.get(service.base + "/v1/events", stream=True, timeout=(5, 5)))
        assert all(r.status_code == 200 for r in opened)
        refused = service.get("/v1/events")
        assert refused.status_code == 503 and refused.json()["error"] == "too_many_streams"
    finally:
        for response in opened:
            response.close()
        service.stop()


# ------------------------------------------------------------ corruption
def _closed_home_with_payloads(tmp_path):
    home = tmp_path / "home"
    ctl = make_controller(home)
    for n in range(40):
        ctl.create_task(task_body(params={"blob": f"marker-{n:03d}-" + "x" * 2000}))
    ctl.stop()  # last connection closed: WAL checkpointed into courier.db
    return home, home / "courier.db"


def _boot_expect_degraded(home, db, reason_part):
    digest = hashlib.sha256(db.read_bytes()).hexdigest()
    ctl = make_controller(home)
    try:
        assert ctl.mode == DEGRADED and reason_part in ctl.degraded_reason, ctl.degraded_reason
        assert api_error(ctl.create_task, task_body()).status == 503
    finally:
        ctl.stop()
    assert hashlib.sha256(db.read_bytes()).hexdigest() == digest, "evidence must be preserved byte for byte"


def test_structural_page_corruption_is_caught_by_quick_check(tmp_path):
    home, db = _closed_home_with_payloads(tmp_path)
    import sqlite3
    conn = sqlite3.connect(str(db))
    root = conn.execute("SELECT rootpage FROM sqlite_master WHERE name = 'events_task'").fetchone()[0]
    page_size = conn.execute("PRAGMA page_size").fetchone()[0]
    conn.close()
    data = bytearray(db.read_bytes())
    offset = (root - 1) * page_size
    data[offset:offset + 8] = b"\xff" * 8  # destroy the b-tree page header
    db.write_bytes(bytes(data))
    _boot_expect_degraded(home, db, "")


def test_single_byte_payload_flip_is_caught_by_the_hash_chain(tmp_path):
    home, db = _closed_home_with_payloads(tmp_path)
    raw = db.read_bytes()
    hits = raw.count(b"marker-017-x")
    assert hits >= 2  # the event row and its projection row
    db.write_bytes(raw.replace(b"marker-017-x", b"marker-017-y"))  # valid JSON, valid pages
    _boot_expect_degraded(home, db, "hash chain broken")
