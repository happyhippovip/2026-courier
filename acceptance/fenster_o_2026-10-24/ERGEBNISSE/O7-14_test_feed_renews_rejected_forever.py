"""O7-14 (G2): a workkey whose mission the controller rejected is renewed forever.

The bridge leaves a refused mission with posted=False and no status
(scripts/ledger_v1_bridge.py:366-369, see O7-15). The feed only releases on
FINAL_DONE and otherwise renews: base 81bbf224 courier_worker/queue_feed.py:123-134;
WQ-1b v2 (claude/v38-wq1b a2a6dfabd) :157-176 parks only for status ERROR/BLOCKED.
A rejected mission has neither, so the holder keeps the lease alive on every pass
and never takes other work. Runs the real feed + real bridge, refusing fake HTTP.
"""
import json

import pytest

from courier_core.work_queue import WorkQueue
from courier_worker import queue_feed
from tests.test_ledger_v1_bridge import AGENT, HOST, TOKEN, FakeHTTP, _run, _spec

HOLDER = "o7-14-holder"


class RefusingHTTP(FakeHTTP):
    def __call__(self, method, url, headers, body, timeout):
        if method == "POST" and url.endswith("/v1/tasks"):
            self.posts.append(json.loads(body.decode("utf-8")))
            return 400, b'{"error":"invalid_request","message":"refused"}'
        return super().__call__(method, url, headers, body, timeout)


def _home(tmp_path):
    home, items_dir = tmp_path / "home", tmp_path / "items"
    (home / "run").mkdir(parents=True)
    items_dir.mkdir()
    (home / "run" / "controller.token").write_text(TOKEN + "\n", encoding="utf-8")
    for item_id in ("WK1", "WK2"):
        row = {"id": item_id, "title": item_id, "lane": "L2", "branch": "lane/L2-" + item_id,
               "files_scope": [f"scope/{item_id}.py"], "depends_on": [], "acceptance": ["tests"],
               "provider_hints": ["headless"], "status": "READY", "lease": None}
        (items_dir / f"{item_id}.json").write_text(json.dumps(row), encoding="utf-8")
    ledger = tmp_path / "queue_ledger.jsonl"
    (home / queue_feed.CONFIG_NAME).write_text(json.dumps({
        "holder": HOLDER, "items_dir": str(items_dir), "ledger": str(ledger),
        "specs": {"WK1": _spec(), "WK2": _spec(params={"unit": "b"})},
    }), encoding="utf-8")
    return home, WorkQueue(items_dir=items_dir, ledger_path=ledger), ledger


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="O7-14/G2: rejected mission without status keeps its workkey renewed forever")
def test_rejected_mission_does_not_hold_its_workkey_forever(tmp_path):
    home, queue, ledger = _home(tmp_path)
    http = RefusingHTTP()
    for _ in range(3):
        queue_feed.feed_once(home, AGENT, HOST)
        _run(home, http)
    renews = [l for l in ledger.read_text(encoding="utf-8").splitlines() if '"RENEW"' in l]
    status = {i["id"]: i["status"] for i in queue.items()}
    # Expected after a fix: WK1 is parked/blocked after the refusal, renewed at most once.
    assert status["WK1"] != "CLAIMED" and len(renews) <= 1, (status, len(renews))
