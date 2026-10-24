"""A crash at any step of feed_once is finished exactly once by the next pass (B09, D09)."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from courier_core.work_queue import WorkQueue
from courier_worker.queue_feed import feed_once
from scripts.coordination_ledger import EventType
from scripts.coordination_resume import reduce_store
from scripts.github_coordination import FileCoordinationStore

T0 = datetime(2026, 10, 23, 12, 0, 0, tzinfo=timezone.utc)
AGENT, HOST = "GOOGLE_WINDOWS", "WINDOWS_REMOTE"


def _spec(content):
    return {"adapter": "synthetic", "params": {"content": content}, "effect_class": "idempotent",
            "max_attempts": 2, "lease_ttl_s": 10}


@pytest.fixture
def home(tmp_path):
    items = tmp_path / "items"
    items.mkdir()
    for key in ("WKA", "WKB"):
        (items / f"{key}.json").write_text(json.dumps({
            "id": key, "title": key, "lane": "L1", "branch": f"lane/L1-{key.lower()}", "files_scope": [f"out/{key}/"],
            "depends_on": [], "acceptance": ["x"], "provider_hints": [], "status": "READY", "lease": None}))
    home = tmp_path / "home"
    home.mkdir()
    (home / "work_queue_feed.json").write_text(json.dumps({
        "items_dir": str(items), "ledger": str(tmp_path / "q.jsonl"), "holder": "h1", "ttl_s": 600,
        "specs": {"WKA": _spec("a"), "WKB": _spec("b")}}))
    return home


def _queue_events(home):
    ledger = home.parent / "q.jsonl"
    return [(e["type"], e["item_id"]) for e in map(json.loads, ledger.read_text().splitlines())
            if e["type"] in ("CLAIM", "RELEASE")]


def _assigned(home):
    reducer = reduce_store(FileCoordinationStore(home / "coordination_ledger.jsonl"))
    return [e.mission_id for e in reducer.events if e.event_type == EventType.ASSIGNED]


def _final_done(home, mission):
    (home / "ledger_bridge_state.json").write_text(json.dumps(
        {"missions": {mission: {"status": "FINAL_DONE", "task_id": f"task-{mission}"}}}))


def test_final_done_stamped_then_crash_before_release_releases_once(home):
    feed_once(home, AGENT, HOST, now=T0)
    _final_done(home, "WKA")                                  # bridge stamped FINAL_DONE, feed died before release
    feed_once(home, AGENT, HOST, now=T0 + timedelta(seconds=1))
    feed_once(home, AGENT, HOST, now=T0 + timedelta(seconds=2))
    assert _queue_events(home) == [("CLAIM", "WKA"), ("RELEASE", "WKA"), ("CLAIM", "WKB")]
    assert _assigned(home) == ["WKA", "WKB"]


def test_crash_between_release_and_next_claim_claims_the_next_once(home, monkeypatch):
    feed_once(home, AGENT, HOST, now=T0)
    _final_done(home, "WKA")

    def killed(self, *args, **kwargs):
        raise SystemExit("killed between release and next claim")
    with monkeypatch.context() as patch:
        patch.setattr(WorkQueue, "claim", killed)
        with pytest.raises(SystemExit):
            feed_once(home, AGENT, HOST, now=T0 + timedelta(seconds=1))
    feed_once(home, AGENT, HOST, now=T0 + timedelta(seconds=2))
    feed_once(home, AGENT, HOST, now=T0 + timedelta(seconds=3))
    assert _queue_events(home) == [("CLAIM", "WKA"), ("RELEASE", "WKA"), ("CLAIM", "WKB")]
    assert _assigned(home) == ["WKA", "WKB"]


def test_crash_between_claim_and_assigned_assigns_once_on_restart(home, monkeypatch):
    def killed(self, event):
        raise SystemExit("killed before the ASSIGNED event")
    with monkeypatch.context() as patch:
        patch.setattr(FileCoordinationStore, "write_event", killed)
        with pytest.raises(SystemExit):
            feed_once(home, AGENT, HOST, now=T0)
    report = feed_once(home, AGENT, HOST, now=T0 + timedelta(seconds=1))
    feed_once(home, AGENT, HOST, now=T0 + timedelta(seconds=2))
    assert report["assigned"] == ["WKA"] and _assigned(home) == ["WKA"]
    assert _queue_events(home) == [("CLAIM", "WKA")]
