"""Desktop Hub must read a real journal, and say UNKNOWN when that source is missing.

A home with no courier.db is not an empty ledger. A home whose courier.db
holds one RUNNING task and one BLOCKED task must project those tasks and a
ledger status from that file. Desktop fixture ids (t-blocked, t-running, …)
are not a stand-in for either case.
"""

import json
import threading
import urllib.request
from pathlib import Path

from courier_core.events import Event, EventType
from courier_core.journal import Journal
from courier_hub.server import Hub, HubServer

FIXTURE_IDS = {"t-blocked", "t-running", "t-verified", "t-human", "t-uncertain", "t-failed"}
RUNNING_ID = "live-running"
BLOCKED_ID = "live-blocked"


def _created(task_id: str, effect_class: str) -> Event:
    return Event(
        type=EventType.TASK_CREATED,
        task_id=task_id,
        payload={
            "adapter": "synthetic",
            "params": {"title": task_id},
            "effect_class": effect_class,
            "max_attempts": 3,
            "lease_ttl_s": 30,
        },
    )


def write_live_journal(home: Path) -> None:
    """Append-only journal: one running task, one blocked non-idempotent task."""
    journal = Journal(home / "courier.db").open()
    try:
        journal.append(_created(RUNNING_ID, "idempotent"))
        journal.append(Event(
            type=EventType.TASK_CLAIMED, task_id=RUNNING_ID, attempt=1,
            dispatch_id="d-running", worker_id="w-run", payload={"ttl_s": 30},
        ))
        journal.append(Event(
            type=EventType.TASK_STARTED, task_id=RUNNING_ID, attempt=1,
            dispatch_id="d-running", worker_id="w-run",
        ))
        journal.append(_created(BLOCKED_ID, "non_idempotent"))
        journal.append(Event(
            type=EventType.TASK_CLAIMED, task_id=BLOCKED_ID, attempt=1,
            dispatch_id="d-blocked", worker_id="w-block", payload={"ttl_s": 30},
        ))
        journal.append(Event(
            type=EventType.TASK_STARTED, task_id=BLOCKED_ID, attempt=1,
            dispatch_id="d-blocked", worker_id="w-block",
        ))
        journal.append(Event(
            type=EventType.LEASE_EXPIRED, task_id=BLOCKED_ID, attempt=1,
            dispatch_id="d-blocked", worker_id="w-block", payload={"reason": "ttl"},
        ))
        journal.append(Event(
            type=EventType.TASK_BLOCKED, task_id=BLOCKED_ID,
            payload={"reason": "lease lost before a non-idempotent effect was known"},
        ))
        report = journal.verify_chain()
        assert report.ok, report.reason
        assert journal.task(RUNNING_ID).status.value == "RUNNING"
        assert journal.task(BLOCKED_ID).status.value == "BLOCKED"
    finally:
        journal.close()


class _Hub:
    def __init__(self, home: Path):
        self.server = HubServer(Hub(home, "http://127.0.0.1:9", actor="desktop:tester"), 0)
        self.thread = threading.Thread(
            target=self.server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True,
        )
        self.thread.start()

    def home(self) -> dict:
        url = self.server.url.rstrip("/") + "/hub/api/home"
        with urllib.request.urlopen(url, timeout=10) as response:
            assert response.status == 200
            return json.loads(response.read().decode("utf-8"))

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)


def _ids(view: dict) -> set:
    return {card["id"] for pile in ("needs_you", "working", "done") for card in view[pile]}


def test_missing_home_is_unknown_not_an_empty_ledger(tmp_path):
    hub = _Hub(tmp_path / "no-ledger")
    try:
        view = hub.home()
    finally:
        hub.stop()
    assert view["truth"] == "not_set_up"
    assert view["ledger"]["status"] == "UNKNOWN"
    assert view["data"] == "keine Daten/UNKNOWN"
    assert view["counts"] is None
    assert _ids(view).isdisjoint(FIXTURE_IDS)


def test_real_journal_projects_running_and_blocked_not_fixtures(tmp_path):
    home = tmp_path / "home"
    write_live_journal(home)
    hub = _Hub(home)
    try:
        view = hub.home()
    finally:
        hub.stop()
    assert view["truth"] == "ok"
    assert [card["id"] for card in view["working"]] == [RUNNING_ID]
    assert [card["id"] for card in view["needs_you"]] == [BLOCKED_ID]
    assert view["done"] == []
    assert _ids(view).isdisjoint(FIXTURE_IDS)
    assert view["counts"] == {"needs_you": 1, "working": 1, "done": 0}
    assert view["ledger"]["status"] == "OK"
    assert view["ledger"]["chain_ok"] is True
    assert view["ledger"]["projection"] == "current"
    assert view.get("data") != "keine Daten/UNKNOWN"
