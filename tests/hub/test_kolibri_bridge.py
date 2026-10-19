"""Kolibri Live Event Bridge V17 tests: evidence-only states, no live data.

Pure unit tests over duck-typed event dicts. No journal, no leases, no
network, no filesystem writes: the bridge under test is read-only by
construction (asserted below).
"""

import inspect
import os

import courier_hub.kolibri_bridge as bridge_mod
from courier_hub.kolibri_bridge import LiveEventBridge, needs_human

_H = "courier journal (courier.db)"
_TS = "2026-10-18T09:00:00Z"
_VERIFIER = {"kind": "adapter", "name": "adapters.synthetic.verify",
             "version": "1", "source_sha256": "0" * 64}


def _ev(seq, kind, task="t-1", **kw):
    event = {"seq": seq, "event_id": f"e-{seq}-{task}-{kind}", "type": kind,
             "task_id": task, "attempt": None, "dispatch_id": None,
             "worker_id": None, "result_id": None, "payload": {},
             "ts_utc": _TS, "dedupe_key": kw.pop("dedupe_key", None)}
    event.update(kw)
    return event


def _created(seq=1, task="t-1", dedupe_key=None, **payload):
    base = {"adapter": "synthetic", "params": {}, "effect_class": "idempotent",
            "max_attempts": 3, "lease_ttl_s": 6}
    base.update(payload)
    return _ev(seq, "TASK_CREATED", task, payload=base, dedupe_key=dedupe_key)


def _happy(task="t-1", start=1, attempt=1, dispatch="d-1", worker="w-1",
           result="r-1"):
    return [
        _created(start, task),
        _ev(start + 1, "TASK_CLAIMED", task, attempt=attempt,
            dispatch_id=dispatch, worker_id=worker, payload={"ttl_s": 6}),
        _ev(start + 2, "TASK_STARTED", task, attempt=attempt,
            dispatch_id=dispatch, worker_id=worker),
        _ev(start + 3, "RESULT_READY", task, attempt=attempt,
            dispatch_id=dispatch, worker_id=worker, result_id=result,
            payload={"artifacts": [{"path": "a", "sha256": "0" * 64}],
                      "outcome": "success"}),
        _ev(start + 4, "RESULT_ACCEPTED", task, attempt=attempt,
            dispatch_id=dispatch, result_id=result,
            payload={"reason": "ok", "verifier": dict(_VERIFIER)}),
        _ev(start + 5, "TASK_COMPLETE", task, attempt=attempt,
            dispatch_id=dispatch, result_id=result),
    ]


def test_happy_path_reaches_done_with_evidence():
    bridge = LiveEventBridge()
    events = _happy()
    bridge.ingest_batch(events)
    snap = bridge.snapshot("t-1", _TS)
    assert snap["state"] == "DONE"
    assert snap["evidence"]["type"] == "TASK_COMPLETE"
    assert snap["evidence"]["seq"] == 6
    assert snap["evidence"]["event_id"] == "e-6-t-1-TASK_COMPLETE"
    assert snap["evidence"]["source"] == _H
    assert snap["reason"] == "verifier-completed"
    assert snap["stale"] is False


def test_ready_vs_queued_needs_dependency_evidence():
    bridge = LiveEventBridge()
    assert bridge.ingest(_created(1, "dep"))["state"] == "READY"
    assert bridge.ingest(_created(2, "child", depends_on="dep"))["state"] == "QUEUED"
    assert bridge.snapshot("child")["reason"] == "waiting-on-dependency"
    for event in _happy("dep", start=2):
        bridge.ingest(event)
    assert bridge.snapshot("dep")["state"] == "DONE"
    assert bridge.snapshot("child")["state"] == "READY"
    assert bridge.snapshot("child")["reason"] == "dependency-verified"


def test_claim_shows_transferred_start_shows_running():
    bridge = LiveEventBridge()
    bridge.ingest(_created())
    assert bridge.ingest(_ev(2, "TASK_CLAIMED", attempt=1, dispatch_id="d",
                             worker_id="w", payload={"ttl_s": 6}))["state"] == "TRANSFERRED"
    assert bridge.ingest(_ev(3, "TASK_STARTED", attempt=1, dispatch_id="d",
                             worker_id="w"))["state"] == "RUNNING"


def test_start_without_claim_stays_unknown():
    bridge = LiveEventBridge()
    bridge.ingest(_created())
    verdict = bridge.ingest(_ev(2, "TASK_STARTED", attempt=1, dispatch_id="d",
                                worker_id="w"))
    assert verdict["state"] == "UNKNOWN"
    assert bridge.snapshot("t-1")["reason"] == "missing-handover-evidence"
    assert needs_human(bridge.snapshot("t-1")) is True


def test_verdict_without_running_and_done_without_verdict_stay_unknown():
    bridge = LiveEventBridge()
    bridge.ingest(_created())
    bridge.ingest(_ev(2, "RESULT_READY", attempt=1, dispatch_id="d",
                       worker_id="w", result_id="r",
                       payload={"artifacts": [{"path": "a", "sha256": "0" * 64}],
                                 "outcome": "success"}))
    assert bridge.snapshot("t-1")["state"] == "UNKNOWN"
    other = LiveEventBridge()
    other.ingest(_created())
    other.ingest(_ev(2, "TASK_COMPLETE", attempt=1, dispatch_id="d",
                      result_id="r"))
    assert other.snapshot("t-1")["state"] == "UNKNOWN"
    assert other.snapshot("t-1")["reason"] == "completion-without-verdict"


def test_accept_without_verifier_identity_is_not_green():
    bridge = LiveEventBridge()
    bridge.ingest_batch(_happy()[:4])
    bridge.ingest(_ev(5, "RESULT_ACCEPTED", attempt=1, dispatch_id="d-1",
                       result_id="r-1", payload={"reason": "ok"}))
    snap = bridge.snapshot("t-1")
    assert (snap["state"], snap["reason"]) == ("UNKNOWN", "verifier-evidence-missing")


def test_human_confirmation_never_done_or_green():
    bridge = LiveEventBridge()
    bridge.ingest(_created())
    bridge.ingest(_ev(2, "EFFECT_CONFIRMED", attempt=1,
                       payload={"actor": "desktop:ana", "reason": "saw it"}))
    snap = bridge.snapshot("t-1")
    assert snap["state"] == "UNKNOWN"
    assert snap["reason"] == "human-confirmed-not-verified"


def test_dedupe_and_conflict():
    bridge = LiveEventBridge()
    bridge.ingest(_created(1, dedupe_key="created:t-1"))
    again = bridge.ingest(_created(1, dedupe_key="created:t-1"))
    assert again["result"] == "duplicate"
    assert bridge.snapshot("t-1")["duplicate_count"] == 1
    assert bridge.snapshot("t-1")["state"] == "READY"
    clash = _created(2)
    clash["dedupe_key"] = "created:t-1"
    clash["payload"] = {"adapter": "other", "params": {},
                        "effect_class": "idempotent", "max_attempts": 3,
                        "lease_ttl_s": 6}
    verdict = bridge.ingest(clash)
    assert verdict["result"] == "conflict"
    assert bridge.snapshot("t-1")["state"] == "UNKNOWN"
    assert bridge.snapshot("t-1")["reason"] == "dedupe-conflict"


def test_out_of_order_buffers_until_gap_fills():
    bridge = LiveEventBridge()
    bridge.ingest(_created(1))
    bridge.ingest(_ev(2, "TASK_CLAIMED", attempt=1, dispatch_id="d",
                       worker_id="w", payload={"ttl_s": 6}))
    buffered = bridge.ingest(_ev(4, "RESULT_READY", attempt=1, dispatch_id="d",
                                  worker_id="w", result_id="r",
                                  payload={"artifacts": [{"path": "a",
                                                          "sha256": "0" * 64}],
                                            "outcome": "success"}))
    assert buffered["result"] == "buffered"
    assert bridge.snapshot("t-1")["state"] == "TRANSFERRED"
    assert bridge.snapshot("t-1")["gap"] == 3
    bridge.ingest(_ev(3, "TASK_STARTED", attempt=1, dispatch_id="d",
                       worker_id="w"))
    snap = bridge.snapshot("t-1")
    assert snap["state"] == "VERIFYING"
    assert snap["gap"] is None


def test_replay_idempotent_restart_equal_no_repulse():
    first = LiveEventBridge()
    first.ingest_batch(_happy())
    pulses = first.pop_pulses()
    assert [(p["state"]) for p in pulses] == ["VERIFIED", "DONE"]
    assert first.pop_pulses() == []
    before = first.snapshot("t-1")
    first.replay(_happy())
    after = first.snapshot("t-1")
    for key in ("state", "reason", "evidence", "history_len"):
        assert after[key] == before[key], key
    assert after["duplicate_count"] > before["duplicate_count"]
    assert first.pop_pulses() == []
    second = LiveEventBridge()
    second.replay(_happy())
    rested = second.snapshot("t-1")
    for key in ("state", "reason", "evidence", "history_len"):
        assert rested[key] == before[key], key
    assert second.pop_pulses() == []


def test_stale_flag_and_late_events_never_change_state():
    bridge = LiveEventBridge()
    bridge.ingest_batch(_happy())
    snap = bridge.snapshot("t-1", "2026-10-18T09:00:00Z")
    assert snap["stale"] is False
    old = bridge.snapshot("t-1", "2026-10-18T12:00:01Z")
    assert old["stale"] is True and old["state"] == "DONE"
    bridge.note_heartbeat("t-1", "2026-10-18T09:00:00Z", alive=False)
    dead = bridge.snapshot("t-1", "2026-10-18T09:00:01Z")
    assert dead["stale"] is True and dead["state"] == "DONE"


def test_blocked_failed_cancel_paths_with_diagnosis():
    bridge = LiveEventBridge()
    bridge.ingest(_created(1, "b"))
    bridge.ingest(_ev(2, "TASK_BLOCKED", "b", payload={"reason": "unsure"}))
    assert bridge.snapshot("b")["state"] == "BLOCKED"
    bridge.ingest(_created(3, "f"))
    bridge.ingest(_ev(4, "TASK_FAILED", "f", payload={"reason": "bad"}))
    assert bridge.snapshot("f")["state"] == "FAILED"
    bridge.ingest(_created(5, "c"))
    bridge.ingest(_ev(6, "TASK_CANCELLED", "c", payload={"reason": "stop"}))
    assert bridge.snapshot("c")["state"] == "UNKNOWN"
    assert bridge.snapshot("c")["reason"] == "cancelled"
    for task in ("b", "f", "c"):
        text = bridge.diagnose(task, _TS)
        assert task in text and "Last evidence:" in text


def test_reconnect_closes_gap():
    bridge = LiveEventBridge()
    bridge.ingest_batch(_happy()[:3])
    journal = _happy()

    def fetch(after):
        return [e for e in journal if e["seq"] > after]

    report = bridge.reconnect(fetch)
    assert report["cursor"] == 6
    assert report["gap"] is None
    assert bridge.snapshot("t-1")["state"] == "DONE"


def test_bridge_is_read_only_by_construction():
    source = inspect.getsource(bridge_mod)
    for token in ("sqlite3", "urllib", "subprocess", "os.write", "os.replace",
                  "socket", "LeaseStore", "Journal", "WorkQueue",
                  "journal.append", "check_write", ".acquire("):
        assert token not in source, token
    for name in ("open(", "__import__", "eval(", "exec("):
        assert name not in source, name
    here = os.getcwd()
    bridge = LiveEventBridge()
    bridge.ingest_batch(_happy())
    bridge.snapshot("t-1")
    assert os.getcwd() == here
