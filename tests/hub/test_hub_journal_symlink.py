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


def test_hub_does_not_read_a_symlinked_token(tmp_path):
    secret = "foreign-token\n"
    outside = tmp_path / "secret-token"
    outside.write_text(secret, encoding="utf-8")
    home = tmp_path / "home"
    run = home / "run"
    run.mkdir(parents=True)
    (run / "controller.token").symlink_to(outside)
    file_hub = Hub(home, "http://127.0.0.1:9", actor="desktop:tester", timeout_s=1)

    outside_run = tmp_path / "outside-run"
    outside_run.mkdir()
    (outside_run / "controller.token").write_text(secret, encoding="utf-8")
    home_dir = tmp_path / "home-dir"
    home_dir.mkdir()
    (home_dir / "run").symlink_to(outside_run, target_is_directory=True)
    dir_hub = Hub(home_dir, "http://127.0.0.1:9", actor="desktop:tester", timeout_s=1)

    found = [file_hub._token(), dir_hub._token()]
    assert found == [None, None], found
    assert outside.read_text(encoding="utf-8") == secret


def test_status_does_not_treat_a_symlinked_journal_as_running(tmp_path, monkeypatch):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "courier.db").write_bytes(b"foreign-journal")
    home = tmp_path / "home"
    home.mkdir()
    (home / "courier.db").symlink_to(outside / "courier.db")

    outside_home = tmp_path / "outside-home"
    outside_home.mkdir()
    (outside_home / "courier.db").write_bytes(b"foreign-home")
    linked_home = tmp_path / "linked-home"
    linked_home.symlink_to(outside_home, target_is_directory=True)

    calls = []

    def fake_call(method, path, body=None):
        calls.append((method, path))
        return 200, {"mode": "ok", "head_seq": 9}

    seen = []
    for label, root in (("file", home), ("home", linked_home)):
        hub = Hub(root, "http://127.0.0.1:9", actor="desktop:tester", timeout_s=1)
        monkeypatch.setattr(hub, "_call", fake_call)
        status = hub.status()
        seen.append((label, status.get("controller"), list(calls)))
        calls.clear()
    assert seen == [("file", "unreadable", []), ("home", "unreadable", [])], seen
    assert (outside / "courier.db").read_bytes() == b"foreign-journal"
