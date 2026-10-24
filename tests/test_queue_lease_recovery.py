"""WQ-1b: an expired lease of another holder is recovered only when nothing can still be running for it.

The decision table (ATTACH / reconcile / human RECLAIM) is in
acceptance/continuation_v7_2026-10-23/WQ-1b_LEASE_RECOVERY_DESIGN.md.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

from courier_core.work_queue import WorkQueue, WorkQueueError, main
from courier_worker.queue_feed import feed_once
from scripts.coordination_ledger import EventType
from scripts.coordination_resume import reduce_store
from scripts.github_coordination import FileCoordinationStore

T0 = datetime(2026, 10, 23, 12, 0, 0, tzinfo=timezone.utc)
LATER = T0 + timedelta(seconds=120)                         # the 60 s lease of holder-a has expired
SPEC = {"adapter": "synthetic", "params": {"write": "out.txt", "content": "a"}, "effect_class": "idempotent",
        "max_attempts": 1, "lease_ttl_s": 10}


def _setup(tmp_path):
    items = tmp_path / "items"
    items.mkdir()
    (items / "WKA.json").write_text(json.dumps({
        "id": "WKA", "title": "a", "lane": "L1", "branch": "lane/L1-wka", "files_scope": ["out/WKA/"],
        "depends_on": [], "acceptance": ["x"], "provider_hints": [], "status": "READY", "lease": None}))
    ledger = tmp_path / "queue.jsonl"
    homes = []
    for name, holder in (("homeA", "holder-a"), ("homeB", "holder-b")):
        home = tmp_path / name
        home.mkdir()
        (home / "work_queue_feed.json").write_text(json.dumps({
            "items_dir": str(items), "ledger": str(ledger), "holder": holder, "ttl_s": 60, "specs": {"WKA": SPEC}}))
        homes.append(home)
    return WorkQueue(items_dir=items, ledger_path=ledger), homes[0], homes[1]


def _assigned(home):
    reducer = reduce_store(FileCoordinationStore(home / "coordination_ledger.jsonl"))
    return [e for e in reducer.events if e.event_type == EventType.ASSIGNED and e.mission_id == "WKA"]


def _view(queue, now=LATER):
    return [i for i in queue.items(now=now) if i["id"] == "WKA"][0]


def _a_posted_and_went_quiet(tmp_path):
    queue, a, b = _setup(tmp_path)
    report = feed_once(a, "GOOGLE_WINDOWS", "WINDOWS_REMOTE", now=T0)
    assert report["claimed"] == ["WKA"] and report["assigned"] == ["WKA"]
    assert _view(queue, T0)["attached"]["holder"] == "holder-a"     # ATTACH is written before ASSIGNED
    return queue, a, b


def _probe(answer):
    seen = []

    def probe(item_id, attached):
        seen.append((item_id, attached["holder"]))
        if isinstance(answer, Exception):
            raise answer
        return answer
    probe.seen = seen
    return probe


# 1
def test_running_elsewhere_is_not_taken_over(tmp_path):
    queue, a, b = _a_posted_and_went_quiet(tmp_path)
    probe = _probe("RUNNING")
    report = feed_once(b, "MUSE_MAC", "MAC_LOCAL", now=LATER, probe=probe)
    assert probe.seen == [("WKA", "holder-a")]
    assert report["claimed"] == [] and report["foreign_expired"] == ["WKA"]
    assert _assigned(b) == []


# 2
def test_complete_and_verified_elsewhere_is_settled_without_a_new_task(tmp_path):
    queue, a, b = _a_posted_and_went_quiet(tmp_path)
    report = feed_once(b, "MUSE_MAC", "MAC_LOCAL", now=LATER, probe=_probe("COMPLETE_VERIFIED"))
    assert report["reconciled"] == ["WKA"] and report["claimed"] == []
    assert _assigned(b) == []
    view = _view(queue)
    assert view["status"] == "DONE"
    with pytest.raises(WorkQueueError, match="NOT_CLAIMABLE"):
        queue.claim("WKA", "holder-b", 60, now=LATER)


# 3
@pytest.mark.parametrize("final", ["FAILED", "CANCELLED"])
def test_a_final_failure_elsewhere_frees_the_workkey_once(tmp_path, final):
    queue, a, b = _a_posted_and_went_quiet(tmp_path)
    report = feed_once(b, "MUSE_MAC", "MAC_LOCAL", now=LATER, probe=_probe(final))
    assert report["reconciled"] == ["WKA"] and report["claimed"] == ["WKA"]
    assert len(_assigned(b)) == 1
    again = feed_once(b, "MUSE_MAC", "MAC_LOCAL", now=LATER, probe=_probe(final))
    assert again["claimed"] == [] and len(_assigned(b)) == 1


# 4
def test_blocked_elsewhere_waits_for_a_human(tmp_path):
    queue, a, b = _a_posted_and_went_quiet(tmp_path)
    report = feed_once(b, "MUSE_MAC", "MAC_LOCAL", now=LATER, probe=_probe("BLOCKED"))
    assert report["claimed"] == [] and report["foreign_expired"] == ["WKA"]
    view = _view(queue)
    assert view["status"] == "READY" and view["expired_lease"]["holder"] == "holder-a"
    with pytest.raises(WorkQueueError, match="NOT_RECONCILABLE"):
        queue.reconcile("WKA", "BLOCKED", "task-x", "holder-b", now=LATER)


# 5
@pytest.mark.parametrize("probe", [None, _probe(OSError("controller unreachable")), _probe(None), _probe("weird")])
def test_no_answer_is_no_takeover(tmp_path, probe):
    queue, a, b = _a_posted_and_went_quiet(tmp_path)
    report = feed_once(b, "MUSE_MAC", "MAC_LOCAL", now=LATER, probe=probe)
    assert report["claimed"] == [] and report["foreign_expired"] == ["WKA"]
    assert _assigned(b) == []
    with pytest.raises(WorkQueueError, match="ATTACHED_ELSEWHERE"):
        queue.claim("WKA", "holder-b", 60, now=LATER)       # the core refuses too, not only the feed


# 6
def test_a_claim_that_was_never_attached_is_taken_over(tmp_path):
    queue, a, b = _setup(tmp_path)
    queue.claim("WKA", "holder-a", 60, host="WINDOWS_REMOTE", now=T0, announce=True)   # died before ATTACH
    probe = _probe("RUNNING")
    report = feed_once(b, "MUSE_MAC", "MAC_LOCAL", now=LATER, probe=probe)
    assert probe.seen == []                                  # nothing was handed off, nothing to ask
    assert report["claimed"] == ["WKA"] and len(_assigned(b)) == 1


def test_a_legacy_claim_without_the_attach_promise_stays_fail_closed(tmp_path):
    queue, a, b = _setup(tmp_path)
    queue.claim("WKA", "holder-a", 60, host="WINDOWS_REMOTE", now=T0)    # old writer: may have assigned
    report = feed_once(b, "MUSE_MAC", "MAC_LOCAL", now=LATER)
    assert report["claimed"] == [] and report["foreign_expired"] == ["WKA"]


# 7
@pytest.mark.parametrize("actor,reason", [("", "a died"), ("dennis", ""), ("dennis", " "), (None, "x"),
                                          ("dennis", "x\ny")])
def test_reclaim_needs_an_actor_and_a_reason(tmp_path, actor, reason):
    queue, a, b = _a_posted_and_went_quiet(tmp_path)
    with pytest.raises(WorkQueueError):
        queue.reclaim("WKA", actor, reason, now=LATER)
    assert _view(queue)["expired_lease"]["holder"] == "holder-a"


def test_reclaim_frees_the_workkey_and_is_recorded(tmp_path):
    queue, a, b = _a_posted_and_went_quiet(tmp_path)
    done = queue.reclaim("WKA", "dennis", "home A is gone for good", now=LATER)
    assert done == {"item_id": "WKA", "status": "READY", "reclaimed_from": "holder-a", "actor": "dennis"}
    rows = [json.loads(line) for line in queue.ledger_path.read_text().splitlines()]
    assert rows[-1]["type"] == "RECLAIM" and rows[-1]["actor"] == "dennis"
    assert rows[-1]["reason"] == "home A is gone for good" and rows[-1]["expired_holder"] == "holder-a"
    report = feed_once(b, "MUSE_MAC", "MAC_LOCAL", now=LATER)
    assert report["claimed"] == ["WKA"] and len(_assigned(b)) == 1


def test_reclaim_refuses_a_live_lease(tmp_path):
    queue, a, b = _a_posted_and_went_quiet(tmp_path)
    with pytest.raises(WorkQueueError, match="LEASE_LIVE"):
        queue.reclaim("WKA", "dennis", "too early", now=T0 + timedelta(seconds=10))


def test_reclaim_from_the_command_line(tmp_path, capsys):
    queue, a, b = _a_posted_and_went_quiet(tmp_path)
    base = ["--items", str(queue.items_dir), "--ledger", str(queue.ledger_path)]
    with pytest.raises(SystemExit):
        main(base + ["reclaim", "--item", "WKA", "--actor", "dennis"])   # --reason is required
    capsys.readouterr()
    assert main(base + ["reclaim", "--item", "WKA", "--actor", "dennis", "--reason", ""]) == 2
    assert capsys.readouterr().err.strip() == "REASON"


# 8
def test_the_old_holder_does_not_silently_get_the_workkey_back_after_reclaim(tmp_path):
    queue, a, b = _a_posted_and_went_quiet(tmp_path)
    queue.reclaim("WKA", "dennis", "home A is gone for good", now=LATER)
    with pytest.raises(WorkQueueError, match="NOT_HOLDER"):
        queue.renew("WKA", "holder-a", 60, now=LATER)       # a late renew does not revive the old lease
    report = feed_once(a, "GOOGLE_WINDOWS", "WINDOWS_REMOTE", now=LATER)
    assert report["claimed"] == [] and report["reclaimed_away"] == ["WKA"]
    assert _view(queue)["lease"] is None
    assert feed_once(b, "MUSE_MAC", "MAC_LOCAL", now=LATER)["claimed"] == ["WKA"]


def test_ledger_replay_rejects_a_malformed_recovery_event(tmp_path):
    queue, a, b = _a_posted_and_went_quiet(tmp_path)
    with queue.ledger_path.open("a") as fh:
        fh.write(json.dumps({"type": "RECLAIM", "item_id": "WKA", "actor": "", "reason": "x",
                             "expired_holder": "holder-a", "at": "2026-10-23T12:02:00Z"}) + "\n")
    with pytest.raises(WorkQueueError, match="UNREADABLE"):
        queue.items(now=LATER)


def test_a_replayed_reclaim_does_not_end_the_next_holders_lease(tmp_path):
    queue, a, b = _a_posted_and_went_quiet(tmp_path)
    queue.reclaim("WKA", "dennis", "home A is gone for good", now=LATER)
    stale = queue.ledger_path.read_text().splitlines()[-1]
    assert feed_once(b, "MUSE_MAC", "MAC_LOCAL", now=LATER)["claimed"] == ["WKA"]
    with queue.ledger_path.open("a") as fh:
        fh.write(stale + "\n")                              # the same RECLAIM line, written twice
    assert _view(queue)["lease"]["holder"] == "holder-b"


# Review follow-ups (R1, R3-R6, R9)
def test_attach_on_a_sticky_pull_request_item_does_not_grow_the_ledger(tmp_path):
    queue, a, b = _setup(tmp_path)
    seed = json.loads((queue.items_dir / "WKA.json").read_text())
    seed["pull_request"] = "123"
    (queue.items_dir / "WKA.json").write_text(json.dumps(seed))
    queue.claim("WKA", "holder-a", 60, now=T0, announce=True)
    size = queue.ledger_path.stat().st_size
    for _ in range(3):
        queue.attach("WKA", "holder-a", "GOOGLE_WINDOWS/WINDOWS_REMOTE", now=T0)
    assert queue.ledger_path.stat().st_size == size


def test_a_lost_race_is_a_wait_not_a_crash(tmp_path):
    queue, a, b = _a_posted_and_went_quiet(tmp_path)

    def probe(item_id, attached):
        queue.reconcile(item_id, "FAILED", "holder-a FAILED", "holder-c", now=LATER)   # another home was faster
        queue.claim(item_id, "holder-c", 60, now=LATER, announce=True)
        return "FAILED"
    report = feed_once(b, "MUSE_MAC", "MAC_LOCAL", now=LATER, probe=probe)
    assert report["claimed"] == [] and report["foreign_expired"] == ["WKA"] and _assigned(b) == []


def test_reclaimed_mark_ends_with_the_next_claim(tmp_path):
    queue, a, b = _a_posted_and_went_quiet(tmp_path)
    queue.reclaim("WKA", "dennis", "home A is gone for good", now=LATER)
    queue.claim("WKA", "holder-a", 60, now=LATER)            # an explicit human/CLI claim gives it back
    assert _view(queue)["reclaimed"] is None


def test_own_expired_attached_work_is_resumed_before_new_work(tmp_path):
    queue, a, b = _a_posted_and_went_quiet(tmp_path)
    (queue.items_dir / "WK0.json").write_text(json.dumps({
        "id": "WK0", "title": "0", "lane": "L1", "branch": "lane/L1-wk0", "files_scope": ["out/WK0/"],
        "depends_on": [], "acceptance": ["x"], "provider_hints": [], "status": "READY", "lease": None}))
    config = json.loads((a / "work_queue_feed.json").read_text())
    config["specs"]["WK0"] = SPEC
    (a / "work_queue_feed.json").write_text(json.dumps(config))
    assert feed_once(a, "GOOGLE_WINDOWS", "WINDOWS_REMOTE", now=LATER)["claimed"] == ["WKA"]


def test_a_dead_one_time_child_can_be_reclaimed(tmp_path):
    queue, a, b = _setup(tmp_path)
    seed = json.loads((queue.items_dir / "WKA.json").read_text())
    seed.update({"id": "TPL", "template": True, "branch": "lane/L1-tpl"})
    (queue.items_dir / "TPL.json").write_text(json.dumps(seed))
    child = queue.spawn("TPL", "m1", now=T0)["item_id"]
    queue.claim(child, "holder-a", 60, now=T0)
    assert queue.reclaim(child, "dennis", "holder died", now=LATER)["reclaimed_from"] == "holder-a"
    assert [i for i in queue.items(now=LATER) if i["id"] == child][0]["status"] == "READY"


def test_open_work_ignores_what_this_home_may_not_take(tmp_path):
    from courier_worker.queue_feed import has_open_work
    queue, a, b = _a_posted_and_went_quiet(tmp_path)
    assert has_open_work(b, now=LATER) is False             # attached elsewhere: nothing to do here
    queue.reclaim("WKA", "dennis", "home A is gone for good", now=LATER)
    assert has_open_work(a, now=LATER) is False             # reclaimed away from A
    assert has_open_work(b, now=LATER) is True


# V8 race findings and D11 (mission ends ERROR/BLOCKED)
@pytest.mark.parametrize("kind", ["RECLAIM", "RECONCILE"])
def test_a_duplicated_recovery_line_does_not_end_a_later_lease_of_the_same_holder(tmp_path, kind):
    queue, a, b = _a_posted_and_went_quiet(tmp_path)
    if kind == "RECLAIM":
        queue.reclaim("WKA", "dennis", "A gone", now=LATER)
    else:
        queue.reconcile("WKA", "FAILED", "holder-a FAILED", "holder-b", now=LATER)
    line = queue.ledger_path.read_text().splitlines()[-1]
    queue.claim("WKA", "holder-b", 60, now=LATER + timedelta(seconds=10), announce=True)   # B dies before ATTACH
    back = LATER + timedelta(seconds=100)
    assert feed_once(a, "GOOGLE_WINDOWS", "WINDOWS_REMOTE", now=back)["claimed"] == ["WKA"]
    with queue.ledger_path.open("a") as fh:
        fh.write(line + "\n")
    assert _view(queue, back)["lease"]["holder"] == "holder-a"


def test_losing_the_lease_between_listing_and_attach_is_reported_not_raised(tmp_path, monkeypatch):
    queue, a, b = _setup(tmp_path)
    real_attach = WorkQueue.attach

    def taken_over_meanwhile(self, item, holder, ref, now=None):
        queue.claim("WKA", "holder-b", 60, now=LATER, announce=True)       # A's lease expired, B was faster
        return real_attach(self, item, holder, ref, now=LATER)
    queue.claim("WKA", "holder-a", 60, now=T0, announce=True)
    monkeypatch.setattr(WorkQueue, "attach", taken_over_meanwhile)
    report = feed_once(a, "GOOGLE_WINDOWS", "WINDOWS_REMOTE", now=T0 + timedelta(seconds=59))
    assert report["lost"] == ["WKA"] and _assigned(a) == []


@pytest.mark.parametrize("status", ["ERROR", "BLOCKED"])
def test_a_mission_that_ends_without_final_parks_the_workkey_and_frees_the_holder(tmp_path, status):
    queue, a, b = _a_posted_and_went_quiet(tmp_path)
    (queue.items_dir / "WKB.json").write_text(json.dumps({
        "id": "WKB", "title": "b", "lane": "L1", "branch": "lane/L1-wkb", "files_scope": ["out/WKB/"],
        "depends_on": [], "acceptance": ["x"], "provider_hints": [], "status": "READY", "lease": None}))
    config = json.loads((a / "work_queue_feed.json").read_text())
    config["specs"]["WKB"] = SPEC
    (a / "work_queue_feed.json").write_text(json.dumps(config))
    (a / "ledger_bridge_state.json").write_text(json.dumps(
        {"missions": {"WKA": {"status": status, "reason": "CONTROLLER_BLOCKED", "task_id": "task-1"}}}))
    report = feed_once(a, "GOOGLE_WINDOWS", "WINDOWS_REMOTE", now=T0 + timedelta(seconds=30))
    assert report["parked"] == ["WKA"] and report["renewed"] == [] and report["claimed"] == ["WKB"]
    view = _view(queue, T0 + timedelta(seconds=30))
    assert view["status"] == "BLOCKED" and view["parked"]["holder"] == "holder-a"
    again = feed_once(a, "GOOGLE_WINDOWS", "WINDOWS_REMOTE", now=T0 + timedelta(seconds=31))
    assert again["parked"] == [] and "WKA" not in again["renewed"]
    # a human decides: reclaim makes it claimable again, the old holder does not quietly retake it
    queue.reclaim("WKA", "dennis", "fixed the input", now=T0 + timedelta(seconds=40))
    assert _view(queue, T0 + timedelta(seconds=40))["status"] == "READY"
    assert feed_once(b, "MUSE_MAC", "MAC_LOCAL", now=T0 + timedelta(seconds=41))["claimed"] == ["WKA"]


def test_park_needs_the_live_holder(tmp_path):
    queue, a, b = _a_posted_and_went_quiet(tmp_path)
    with pytest.raises(WorkQueueError, match="NOT_HOLDER"):
        queue.park("WKA", "holder-b", "ERROR x", now=T0)
    with pytest.raises(WorkQueueError, match="NOT_HOLDER"):
        queue.park("WKA", "holder-a", "ERROR x", now=LATER)          # expired: not ours to park any more
