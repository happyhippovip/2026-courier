"""The hub must not treat a symlinked courier.db as its own journal."""

from pathlib import Path

from courier_core.events import Event, EventType
from courier_core.journal import Journal
from courier_hub.server import Hub

_CREATED = {
    "adapter": "synthetic",
    "params": {"title": "Foreign parcel"},
    "effect_class": "idempotent",
    "max_attempts": 3,
    "lease_ttl_s": 6,
}


def test_hub_does_not_read_a_symlinked_journal(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    with Journal(outside / "courier.db") as journal:
        journal.append(Event(type=EventType.TASK_CREATED, task_id="foreign", payload=dict(_CREATED)))
        journal.append(Event(
            type=EventType.TASK_CLAIMED, task_id="foreign", attempt=1, dispatch_id="d1", worker_id="w1",
            payload={"ttl_s": 6},
        ))
        journal.append(Event(
            type=EventType.TASK_STARTED, task_id="foreign", attempt=1, dispatch_id="d1", worker_id="w1",
        ))
    home = tmp_path / "home"
    home.mkdir()
    (home / "courier.db").symlink_to(outside / "courier.db")
    hub = Hub(Path(home), "http://127.0.0.1:9", actor="desktop:tester", timeout_s=1)
    view = hub.home_view()
    assert view["truth"] == "unreadable", (view["truth"], view["counts"])
    assert view["counts"] == {"needs_you": 0, "working": 0, "done": 0}
