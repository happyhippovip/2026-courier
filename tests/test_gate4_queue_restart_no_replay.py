"""Gate 4: kill and restart the queue -> ledger -> controller path at each phase.

Synthetic only: in-memory controller double, no worker process, no provider.
One process death per case; a "restart" is a fresh call of the one-shot
entry points (courier_worker.queue_feed.feed_once and the bridge main).

Phases:
- before_claim: nothing durable yet
- after_queue_claim: CLAIM is in the queue ledger, ASSIGNED was never written
- after_result: the controller holds A's accepted result, the bridge has not fed it back
- before_final: the bridge dies while appending A's FINAL
- after_final: FINAL is in the ledger, the queue release never happened

Each case must end with CLAIM A, RELEASE A, CLAIM B, RELEASE B in the queue,
exactly one controller post and one FINAL per workkey, and a replay that
changes nothing.
"""

import json
from collections import Counter

import pytest

from courier_core.work_queue import WorkQueue
from courier_worker import queue_feed
from scripts.coordination_ledger import EventType
from scripts.coordination_resume import reduce_store
from scripts.github_coordination import FileCoordinationStore
from tests.test_ledger_v1_bridge import AGENT, HOST, SHA, FakeHTTP, _home, _run

PHASES = ("before_claim", "after_queue_claim", "after_result", "before_final", "after_final")
HOLDER = "worker-gate4"


class Killed(Exception):
    pass


def _item(item_id, deps):
    return {"id": item_id, "title": f"synthetic {item_id}", "lane": "L1",
            "branch": f"lane/L1-{item_id.lower()}", "files_scope": [f"out/{item_id}/"],
            "depends_on": deps, "acceptance": ["synthetic artifact"], "provider_hints": [],
            "status": "READY", "lease": None}


def _spec(unit):
    return {"adapter": "synthetic", "params": {"unit": unit}, "effect_class": "idempotent",
            "max_attempts": 1, "lease_ttl_s": 30, "source_sha": SHA}


def _setup(tmp_path):
    home = _home(tmp_path, {})
    items = tmp_path / "items"
    items.mkdir()
    (items / "WKA.json").write_text(json.dumps(_item("WKA", [])), encoding="utf-8")
    (items / "WKB.json").write_text(json.dumps(_item("WKB", ["WKA"])), encoding="utf-8")
    ledger = tmp_path / "queue.jsonl"
    (home / queue_feed.CONFIG_NAME).write_text(json.dumps({
        "items_dir": str(items), "ledger": str(ledger), "holder": HOLDER, "ttl_s": 600,
        "specs": {"WKA": _spec("a"), "WKB": _spec("b")}}), encoding="utf-8")
    return home, WorkQueue(items_dir=items, ledger_path=ledger), ledger


def _queue_seq(ledger):
    if not ledger.exists():
        return []
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line]
    return [(r["type"], r["item_id"]) for r in rows if r["type"] in ("CLAIM", "RELEASE")]


def _events(home):
    return reduce_store(FileCoordinationStore(home / "coordination_ledger.jsonl")).events


def _complete_posted(http):
    for task_id, view in http.views.items():
        if view["status"] != "COMPLETE":
            view.update(status="COMPLETE", attempt=1, accepted_result_id="result-" + task_id[-6:])


def _tick(home, http):
    """One idle tick as LedgerTick runs it: queue feed, then one bridge pass."""
    queue_feed.feed_once(home, AGENT, HOST)
    code, _out, err, _log, _lines = _run(home, http)
    assert code == 0, err


def _kill_at(phase, home, http, monkeypatch):
    if phase == "before_claim":
        return
    if phase == "after_queue_claim":
        original = FileCoordinationStore.write_event

        def die(self, event):
            raise Killed("died after CLAIM, before ASSIGNED")
        monkeypatch.setattr(FileCoordinationStore, "write_event", die)
        with pytest.raises(Killed):
            queue_feed.feed_once(home, AGENT, HOST)
        monkeypatch.setattr(FileCoordinationStore, "write_event", original)
        assert ("CLAIM", "WKA") in _queue_seq(home.parent / "queue.jsonl")
        assert not _events(home)
        return
    _tick(home, http)                      # claim + assign + post A
    assert len(http.posts) == 1
    _complete_posted(http)                 # controller holds A's result
    if phase == "after_result":
        return
    if phase == "before_final":
        original = FileCoordinationStore.write_event

        def die(self, event):
            if event.event_type == EventType.FINAL:
                raise Killed("died while appending FINAL")
            return original(self, event)
        monkeypatch.setattr(FileCoordinationStore, "write_event", die)
        with pytest.raises(Killed):
            _run(home, http)
        monkeypatch.setattr(FileCoordinationStore, "write_event", original)
        assert not [e for e in _events(home) if e.event_type == EventType.FINAL]
        return
    if phase == "after_final":
        _run(home, http)                   # FINAL A written
        assert [e.mission_id for e in _events(home) if e.event_type == EventType.FINAL] == ["WKA"]
        original = WorkQueue.release

        def die(self, *a, **k):
            raise Killed("died before queue release")
        monkeypatch.setattr(WorkQueue, "release", die)
        with pytest.raises(Killed):
            queue_feed.feed_once(home, AGENT, HOST)
        monkeypatch.setattr(WorkQueue, "release", original)
        assert ("RELEASE", "WKA") not in _queue_seq(home.parent / "queue.jsonl")
        return
    raise AssertionError(phase)


@pytest.mark.parametrize("phase", PHASES)
def test_queue_path_restart_has_no_replay(tmp_path, monkeypatch, phase):
    home, queue, ledger = _setup(tmp_path)
    http = FakeHTTP()
    _kill_at(phase, home, http, monkeypatch)

    for _ in range(12):                    # restarted process: plain ticks only
        _tick(home, http)
        _complete_posted(http)
        if all(i["status"] == "DONE" for i in queue.items()):
            break
    else:
        raise AssertionError(f"not drained: {_queue_seq(ledger)}")

    assert _queue_seq(ledger) == [("CLAIM", "WKA"), ("RELEASE", "WKA"), ("CLAIM", "WKB"), ("RELEASE", "WKB")]
    assert sorted(p["params"]["unit"] for p in http.posts) == ["a", "b"]
    assert len({p["idempotency_key"] for p in http.posts}) == 2
    events = _events(home)
    counts = Counter((e.mission_id, e.event_type) for e in events)
    assert counts["WKA", EventType.FINAL] == 1 and counts["WKB", EventType.FINAL] == 1, counts
    assert counts["WKA", EventType.ASSIGNED] == 1 and counts["WKB", EventType.ASSIGNED] == 1, counts

    frozen = (_queue_seq(ledger), (home / "coordination_ledger.jsonl").read_text(encoding="utf-8"), list(http.posts))
    for _ in range(3):
        _tick(home, http)
    assert (_queue_seq(ledger), (home / "coordination_ledger.jsonl").read_text(encoding="utf-8"), list(http.posts)) == frozen


def test_blocked_workkey_does_not_block_the_session_across_restart(tmp_path):
    """A parked workkey stays parked (no post, no release, dependents wait),
    but an independent workkey still runs. BLOCKED_WORKKEY != BLOCKED_SESSION."""
    home, queue, ledger = _setup(tmp_path)
    items = tmp_path / "items"
    (items / "WKC.json").write_text(json.dumps(_item("WKC", [])), encoding="utf-8")
    config = json.loads((home / queue_feed.CONFIG_NAME).read_text(encoding="utf-8"))
    bad = _spec("a")
    bad["goal_id"] = "only-id"            # half goal binding: bridge parks it
    config["specs"] = {"WKA": bad, "WKB": _spec("b"), "WKC": _spec("c")}
    (home / queue_feed.CONFIG_NAME).write_text(json.dumps(config), encoding="utf-8")
    http = FakeHTTP()
    for _ in range(8):                    # every tick is a fresh process
        _tick(home, http)
        _complete_posted(http)
    status = {i["id"]: i["status"] for i in queue.items()}
    assert status["WKC"] == "DONE", (status, _queue_seq(ledger))
    assert status["WKB"] == "READY" or status["WKB"] != "DONE"
    assert ("RELEASE", "WKA") not in _queue_seq(ledger)
    assert ("CLAIM", "WKB") not in _queue_seq(ledger)
    assert [p["params"]["unit"] for p in http.posts] == ["c"]
    claims_a = [s for s in _queue_seq(ledger) if s == ("CLAIM", "WKA")]
    assert len(claims_a) == 1, _queue_seq(ledger)
