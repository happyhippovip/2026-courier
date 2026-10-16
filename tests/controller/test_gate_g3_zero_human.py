"""Gate G3 preparation: judge an A→B journal, and skip the Windows-core proof.

The canonical service proof is commit ad7dbc2c42273b755d8daefa16ad8762e55b1a07.
That commit is read and not modified. Its LiveService worker loop, depends_on,
and from_input path are not in this tree. The skipped test is that path.

A fixture can lock the judge. A fixture does not prove Gate 3. The judge never
reports a verification.
"""

import sqlite3

import pytest

from ctrl_helpers import FakeClock, make_controller, run_attempt, task_body
from courier_core.events import Event, EventType
from courier_core.gate_g3 import WINDOWS_CORE_SKIP_REASON, assess_gate_g3
from courier_core.journal import Journal
from courier_core.state_machine import TaskStatus

A = "task-a"
B = "task-b"


class _MemoryJournal:
    def __init__(self, events, ok=True):
        self._events = list(events)
        self._ok = ok

    def verify_chain(self):
        return _Chain(self._ok)

    def events(self):
        return iter(self._events)


class _Chain:
    def __init__(self, ok):
        self.ok = ok


class _Bare:
    def __init__(self, seq, type):
        self.seq = seq
        self.type = type
        self.task_id = None
        self.payload = {}


def _created(depends_on=None):
    payload = {"adapter": "probe", "params": {}, "effect_class": "idempotent",
               "max_attempts": 1, "lease_ttl_s": 6}
    if depends_on is not None:
        payload["depends_on"] = depends_on
    return payload


def _canonical_events():
    """The shape commit ad7dbc2 runs: A finishes, the controller restarts, then B."""
    return [
        Event(type=EventType.CONTROLLER_STARTED, seq=1),
        Event(type=EventType.TASK_CREATED, seq=2, task_id=A, payload=_created()),
        Event(type=EventType.TASK_CREATED, seq=3, task_id=B, payload=_created(A)),
        Event(type=EventType.TASK_CLAIMED, seq=4, task_id=A, attempt=1, dispatch_id="dsp-a",
              worker_id="w1", payload={"ttl_s": 6}),
        Event(type=EventType.RESULT_ACCEPTED, seq=5, task_id=A, attempt=1, dispatch_id="dsp-a",
              result_id="res-a"),
        Event(type=EventType.TASK_COMPLETE, seq=6, task_id=A, attempt=1, dispatch_id="dsp-a",
              result_id="res-a"),
        Event(type=EventType.CONTROLLER_STOPPED, seq=7),
        Event(type=EventType.CONTROLLER_STARTED, seq=8),
        Event(type=EventType.TASK_CLAIMED, seq=9, task_id=B, attempt=1, dispatch_id="dsp-b",
              worker_id="w2", payload={"ttl_s": 6}),
        Event(type=EventType.RESULT_ACCEPTED, seq=10, task_id=B, attempt=1, dispatch_id="dsp-b",
              result_id="res-b"),
        Event(type=EventType.TASK_COMPLETE, seq=11, task_id=B, attempt=1, dispatch_id="dsp-b",
              result_id="res-b"),
    ]


def test_canonical_windows_core_a_to_b_is_skipped_not_passed():
    """Hardware and the ad7dbc2 service harness stay skipped. A skip is not a pass."""
    pytest.skip(WINDOWS_CORE_SKIP_REASON)
    raise AssertionError("the Windows-core path must not pass on this tree")


def test_skip_reason_names_the_canonical_commit_and_refuses_a_pass():
    reason = WINDOWS_CORE_SKIP_REASON
    assert "ad7dbc2c42273b755d8daefa16ad8762e55b1a07" in reason
    assert "not a pass" in reason
    assert "not VERIFIED" in reason


def test_unknown_journal_is_a_failure():
    report = assess_gate_g3(None)
    assert report.status == "FAIL"
    assert report.human_relay_count is None
    assert report.ledger_ok is None
    assert report.verified is False
    assert "unknown" in report.reason


def test_unknown_ledger_flag_is_a_failure_and_events_stay_unread():
    class _Unread:
        def verify_chain(self):
            return _Chain(None)

        def events(self):
            raise AssertionError("events must stay unread when the ledger is unknown")

    report = assess_gate_g3(_Unread())
    assert report.status == "FAIL"
    assert report.ledger_ok is None
    assert report.human_relay_count is None
    assert report.verified is False


def test_unknown_event_type_is_a_failure():
    report = assess_gate_g3(_MemoryJournal([_Bare(1, "NOT_A_COURIER_EVENT")], ok=True))
    assert report.status == "FAIL"
    assert report.human_relay_count is None
    assert "unknown" in report.reason
    assert report.verified is False


def test_broken_hash_chain_is_not_a_measured_zero(tmp_path):
    home = tmp_path / "home"
    ctl = make_controller(home)
    ctl.create_task(task_body())
    db = ctl.db_path
    ctl.stop()
    conn = sqlite3.connect(db)
    conn.execute("DROP TRIGGER IF EXISTS events_no_update")
    conn.execute("UPDATE events SET hash = ? WHERE seq = 1", ("0" * 64,))
    conn.commit()
    conn.close()
    journal = Journal(db, readonly=True).open()
    try:
        report = assess_gate_g3(journal)
    finally:
        journal.close()
    assert report.status == "FAIL"
    assert report.ledger_ok is False
    assert report.human_relay_count is None
    assert report.verified is False


def test_caller_cannot_supply_the_relay_count():
    with pytest.raises(TypeError):
        assess_gate_g3(_MemoryJournal([]), human_relay_count=0)


def test_measured_zero_on_an_empty_ledger_is_not_a_pass():
    report = assess_gate_g3(_MemoryJournal([]))
    assert report.human_relay_count == 0
    assert report.status == "FAIL"
    assert report.verified is False


def test_a_human_retry_is_measured_and_fails(tmp_path):
    home, clock = tmp_path / "home", FakeClock()
    ctl = make_controller(home, clock=clock)
    try:
        _, body = ctl.create_task(task_body(effect_class="non_idempotent", lease_ttl_s=6))
        lease = ctl.claim({"worker_id": "w1"})
        ctl.start({"dispatch_id": lease["dispatch_id"]})
        elapsed = 0.0
        while elapsed < 10:
            clock.advance(0.25)
            elapsed += 0.25
            ctl.tick()
        assert ctl.journal.task(body["task_id"]).status is TaskStatus.BLOCKED
        ctl.resolve(body["task_id"], {
            "decision": "retry_authorized", "actor": "ops", "attempt": 1, "reason": "checked",
        })
        report = assess_gate_g3(ctl.journal)
    finally:
        ctl.stop()
    assert report.human_relay_count == 1
    assert report.status == "FAIL"
    assert report.ledger_ok is True
    assert report.verified is False


def test_trunk_restart_does_not_pass_without_a_recorded_dependency(tmp_path):
    """This controller can finish A and later B. It does not record depends_on.

    The measured relay count is 0 and the chain is intact, and the judge still
    fails. That failure is the local result. It is not a Windows-core pass.
    """
    home = tmp_path / "home"
    ctl = make_controller(home)
    _, created = ctl.create_task(task_body())
    run_attempt(ctl, result_id="res-a")
    ctl.drain()
    assert ctl.journal.task(created["task_id"]).status is TaskStatus.COMPLETE
    ctl.stop()
    ctl = make_controller(home)
    try:
        ctl.create_task(task_body())
        run_attempt(ctl, worker="w2", result_id="res-b")
        ctl.drain()
        report = assess_gate_g3(ctl.journal)
        claimed_a = [
            event for event in ctl.journal.events(task_id=created["task_id"])
            if event.type is EventType.TASK_CLAIMED
        ]
    finally:
        ctl.stop()
    assert len(claimed_a) == 1
    assert report.human_relay_count == 0
    assert report.ledger_ok is True
    assert report.replay is False
    assert report.status == "FAIL"
    assert "depends_on" in report.reason
    assert report.verified is False


def test_judge_pass_requires_measured_zero_a_complete_ledger_and_no_replay():
    """Locks the judge. These events are a fixture, not a Gate 3 proof."""
    report = assess_gate_g3(_MemoryJournal(_canonical_events()))
    assert report.human_relay_count == 0
    assert report.ledger_ok is True
    assert report.replay is False
    assert report.status == "PASS"
    assert report.verified is False


def test_a_second_claim_of_a_after_restart_is_a_replay():
    events = _canonical_events()
    events.append(Event(
        type=EventType.TASK_CLAIMED, seq=12, task_id=A, attempt=2, dispatch_id="dsp-a2",
        worker_id="w3", payload={"ttl_s": 6},
    ))
    report = assess_gate_g3(_MemoryJournal(events))
    assert report.replay is True
    assert report.human_relay_count == 0
    assert report.status == "FAIL"
    assert "replay" in report.reason
    assert report.verified is False
