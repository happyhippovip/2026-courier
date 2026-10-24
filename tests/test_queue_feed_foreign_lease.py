"""queue_feed must not take over an expired lease of another holder: the mission may still be running."""
import json
from datetime import datetime, timedelta, timezone

from courier_core.work_queue import WorkQueue
from courier_worker.queue_feed import feed_once
from scripts.coordination_ledger import EventType
from scripts.coordination_resume import reduce_store
from scripts.github_coordination import FileCoordinationStore

T0 = datetime(2026, 10, 23, 12, 0, 0, tzinfo=timezone.utc)
SPEC = {"adapter": "synthetic", "params": {"write": "out.txt", "content": "a"}, "effect_class": "idempotent",
        "max_attempts": 1, "lease_ttl_s": 10}


def _setup(tmp_path, homes, holders):
    items = tmp_path / "items"
    items.mkdir()
    (items / "WKA.json").write_text(json.dumps({
        "id": "WKA", "title": "a", "lane": "L1", "branch": "lane/L1-wka", "files_scope": ["out/WKA/"],
        "depends_on": [], "acceptance": ["x"], "provider_hints": [], "status": "READY", "lease": None}))
    ledger = tmp_path / "queue.jsonl"
    for home, holder in zip(homes, holders):
        home.mkdir()
        (home / "work_queue_feed.json").write_text(json.dumps({
            "items_dir": str(items), "ledger": str(ledger), "holder": holder, "ttl_s": 60, "specs": {"WKA": SPEC}}))
    return WorkQueue(items_dir=items, ledger_path=ledger)


def _assigned(home):
    reducer = reduce_store(FileCoordinationStore(home / "coordination_ledger.jsonl"))
    return [e for e in reducer.events if e.event_type == EventType.ASSIGNED and e.mission_id == "WKA"]


def test_same_home_same_holder_reclaims_after_expiry_without_a_second_assignment(tmp_path):
    home = tmp_path / "home"
    queue = _setup(tmp_path, [home], ["h1"])
    assert feed_once(home, "GOOGLE_WINDOWS", "WINDOWS_REMOTE", now=T0)["claimed"] == ["WKA"]
    later = T0 + timedelta(seconds=120)                     # lease (60 s) expired, mission still running
    report = feed_once(home, "GOOGLE_WINDOWS", "WINDOWS_REMOTE", now=later)
    assert len(_assigned(home)) == 1


def test_an_expired_lease_of_another_holder_is_not_taken_over(tmp_path):
    a, b = tmp_path / "homeA", tmp_path / "homeB"
    queue = _setup(tmp_path, [a, b], ["holder-a", "holder-b"])
    assert feed_once(a, "GOOGLE_WINDOWS", "WINDOWS_REMOTE", now=T0)["claimed"] == ["WKA"]
    later = T0 + timedelta(seconds=120)                     # holder-a went quiet, its mission may still run
    report_b = feed_once(b, "MUSE_MAC", "MAC_LOCAL", now=later)
    assert report_b["claimed"] == [] and report_b["assigned"] == []
    assert report_b["foreign_expired"] == ["WKA"]
    assert len(_assigned(b)) == 0                            # no second mission, so no second controller task
    view = [i for i in queue.items(now=later) if i["id"] == "WKA"][0]
    assert view["lease"] is None and view["expired_lease"]["holder"] == "holder-a"


def test_the_original_holder_can_still_resume_after_its_lease_expired(tmp_path):
    a, b = tmp_path / "homeA", tmp_path / "homeB"
    _setup(tmp_path, [a, b], ["holder-a", "holder-b"])
    feed_once(a, "GOOGLE_WINDOWS", "WINDOWS_REMOTE", now=T0)
    later = T0 + timedelta(seconds=120)
    feed_once(b, "MUSE_MAC", "MAC_LOCAL", now=later)
    assert feed_once(a, "GOOGLE_WINDOWS", "WINDOWS_REMOTE", now=later)["claimed"] == ["WKA"]
    assert len(_assigned(a)) == 1
