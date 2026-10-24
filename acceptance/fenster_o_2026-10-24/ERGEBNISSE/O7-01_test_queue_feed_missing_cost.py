"""O7-01 (B1 CostGate): a workkey whose task spec has no estimated_cost_eur
must not occupy the queue. Today queue_feed claims and assigns it without any
cost check (courier_worker/queue_feed.py:131-142), the bridge refuses it every
pass with UNKNOWN_COST (scripts/ledger_v1_bridge.py:259-271) and nothing parks
it, so the holder keeps renewing the lease (queue_feed.py:133) and the next,
fully costed workkey is never claimed. Fail-closed on cost, but the queue stalls.
"""
import json

import pytest

from courier_core.work_queue import WorkQueue
from courier_worker import queue_feed
from tests.test_ledger_v1_bridge import AGENT, HOST, TOKEN, FakeHTTP, _run, _spec

HOLDER = "o7-01-holder"


def _item(item_id):
    return {"id": item_id, "title": "Item " + item_id, "lane": "L2", "branch": "lane/L2-" + item_id,
            "files_scope": [f"scope/{item_id}.py"], "depends_on": [], "acceptance": ["tests"],
            "provider_hints": ["headless"], "status": "READY", "lease": None}


def _home(tmp_path, specs):
    home = tmp_path / "home"
    items_dir = tmp_path / "items"
    (home / "run").mkdir(parents=True)
    items_dir.mkdir()
    (home / "run" / "controller.token").write_text(TOKEN + "\n", encoding="utf-8")
    for item_id in specs:
        (items_dir / f"{item_id}.json").write_text(json.dumps(_item(item_id)), encoding="utf-8")
    ledger = tmp_path / "queue_ledger.jsonl"
    (home / queue_feed.CONFIG_NAME).write_text(json.dumps({
        "holder": HOLDER, "items_dir": str(items_dir), "ledger": str(ledger), "specs": specs,
    }), encoding="utf-8")
    return home, WorkQueue(items_dir=items_dir, ledger_path=ledger)


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="O7-01/B1: a spec without estimated_cost_eur holds the queue forever")
def test_workkey_without_cost_estimate_does_not_block_the_next_workkey(tmp_path):
    no_cost = _spec()
    del no_cost["estimated_cost_eur"]
    home, queue = _home(tmp_path, {"WK1": no_cost, "WK2": _spec(params={"unit": "b"})})
    http = FakeHTTP()
    for _ in range(3):
        queue_feed.feed_once(home, AGENT, HOST)
        _run(home, http)
    # The guard that already holds today: nothing without an estimate reaches the controller.
    assert {"unit": "a"} not in [post["params"] for post in http.posts]
    status = {i["id"]: i.get("status") for i in queue.items()}
    # Expected after a fix: WK1 is parked/blocked (not CLAIMED forever) and WK2 is dispatched.
    assert status["WK1"] != "CLAIMED"
    assert [post["params"] for post in http.posts] == [{"unit": "b"}]
