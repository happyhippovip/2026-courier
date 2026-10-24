"""O7-03 (B2 Single Writer): two writers at the same time on courier_core/work_queue.py.

Guard (holds on the base): two different holders racing for one item -> exactly one
CLAIM, the other gets DUPLICATE_CLAIM (lock courier_core/work_queue.py:242-279,
check work_queue.py:101-104).

Defect (strict xfail): the idempotent re-claim at work_queue.py:102-103 compares only
the holder string, not the host. Two writers on different hosts that carry the same
holder name (copied work_queue_feed.json, courier_worker/queue_feed.py:93) both get
a successful claim and both treat the item as theirs: two writers, one lease.
"""
import json
import threading

import pytest

from courier_core.work_queue import WorkQueue, WorkQueueError


def _queue(tmp_path):
    items = tmp_path / "items"
    items.mkdir()
    row = {"id": "WK1", "title": "Item WK1", "lane": "L2", "branch": "lane/L2-WK1",
           "files_scope": ["scope/WK1.py"], "depends_on": [], "acceptance": ["tests"],
           "provider_hints": ["headless"], "status": "READY", "lease": None}
    (items / "WK1.json").write_text(json.dumps(row), encoding="utf-8")
    return items, tmp_path / "ledger.jsonl"


def _race(items, ledger, writers):
    barrier = threading.Barrier(len(writers))
    results = {}

    def run(name, holder, host):
        queue = WorkQueue(items_dir=items, ledger_path=ledger)  # own instance = own lock fd
        barrier.wait()
        try:
            results[name] = queue.claim("WK1", holder, 600, host=host)
        except WorkQueueError as exc:
            results[name] = str(exc)

    threads = [threading.Thread(target=run, args=w) for w in writers]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    claims = [line for line in ledger.read_text(encoding="utf-8").splitlines() if '"CLAIM"' in line]
    return results, claims


def test_guard_two_holders_racing_get_exactly_one_claim(tmp_path):
    items, ledger = _queue(tmp_path)
    for _ in range(20):
        ledger.unlink(missing_ok=True)
        results, claims = _race(items, ledger, [("a", "writer-a", "MAC"), ("b", "writer-b", "WIN")])
        wins = [r for r in results.values() if isinstance(r, dict)]
        assert len(wins) == 1 and len(claims) == 1
        assert "DUPLICATE_CLAIM" in results.values()


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="O7-03/B2: same holder name on two hosts -> both writers hold WK1")
def test_same_holder_name_on_two_hosts_is_not_two_writers(tmp_path):
    items, ledger = _queue(tmp_path)
    results, claims = _race(items, ledger, [("mac", "integrator", "MAC"), ("win", "integrator", "WIN")])
    wins = [r for r in results.values() if isinstance(r, dict)]
    assert len(claims) == 1
    # Expected after a fix: the writer on the other host is refused (not an idempotent success).
    assert len(wins) == 1, results
