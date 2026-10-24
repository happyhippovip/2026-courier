"""O7-05 (B3): a provider/bridge DONE without a FINAL in the coordination journal is not final.

courier_worker/queue_feed.py:125-128 releases a held workkey as DONE as soon as
<home>/ledger_bridge_state.json says ``status: FINAL_DONE``. It never asks the
coordination ledger (the journal the bridge writes FINAL into,
scripts/ledger_v1_bridge.py:200-238) whether that mission is DONE. A state file that
says FINAL_DONE (stale copy, foreign writer, partial restore) closes the workkey for
good with no FINAL event behind it.
Guard (holds): the bridge itself writes the ledger event before it stamps FINAL_DONE.
"""
import json

import pytest

from courier_core.work_queue import WorkQueue
from courier_worker import queue_feed
from scripts.coordination_resume import reduce_store
from scripts.github_coordination import FileCoordinationStore
from scripts.coordination_ledger import MissionStatus
from tests.test_ledger_v1_bridge import AGENT, HOST, _spec

HOLDER = "o7-05-holder"


def _home(tmp_path):
    home = tmp_path / "home"
    items_dir = tmp_path / "items"
    home.mkdir()
    items_dir.mkdir()
    row = {"id": "WK1", "title": "Item WK1", "lane": "L2", "branch": "lane/L2-WK1",
           "files_scope": ["scope/WK1.py"], "depends_on": [], "acceptance": ["tests"],
           "provider_hints": ["headless"], "status": "READY", "lease": None}
    (items_dir / "WK1.json").write_text(json.dumps(row), encoding="utf-8")
    ledger = tmp_path / "queue_ledger.jsonl"
    (home / queue_feed.CONFIG_NAME).write_text(json.dumps({
        "holder": HOLDER, "items_dir": str(items_dir), "ledger": str(ledger), "specs": {"WK1": _spec()},
    }), encoding="utf-8")
    return home, WorkQueue(items_dir=items_dir, ledger_path=ledger)


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="O7-05/B3: queue_feed releases DONE from the bridge state file, not from the journal")
def test_final_done_in_state_without_journal_final_does_not_release(tmp_path):
    home, queue = _home(tmp_path)
    assert queue_feed.feed_once(home, AGENT, HOST)["claimed"] == ["WK1"]
    # Only ASSIGNED is in the journal. Nobody ran the task; there is no FINAL.
    mission = reduce_store(FileCoordinationStore(home / "coordination_ledger.jsonl")).get_mission("WK1")
    assert mission is not None and mission.get("status") != MissionStatus.DONE
    (home / "ledger_bridge_state.json").write_text(json.dumps({"missions": {"WK1": {
        "task_id": "task-x", "idempotency_key": "ledger:x", "posted": True,
        "accepted_result_id": "res-x", "status": "FINAL_DONE",
    }}}), encoding="utf-8")
    report = queue_feed.feed_once(home, AGENT, HOST)
    status = {i["id"]: i["status"] for i in queue.items()}
    # Expected after a fix: no release without a FINAL/DONE mission in the journal.
    assert report["released"] == [] and status["WK1"] == "CLAIMED", (report, status)
