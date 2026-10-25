"""GOAL-07: feed_once passes admission done_prs and open_pr_files into the queue."""
import json
from datetime import datetime, timezone

import pytest

from courier_core.work_queue import WorkQueue
from courier_worker.queue_feed import feed_once, has_open_work

NOW = datetime(2026, 10, 24, 18, 0, 0, tzinfo=timezone.utc)
AGENT = "GOOGLE_MAC"
HOST = "MAC_LOCAL"
HOLDER = "worker-g1"


def _make_item(item_id: str, files_scope: list[str], depends_on: list[str]) -> dict:
    return {
        "id": item_id,
        "title": f"Task {item_id}",
        "lane": "L2",
        "branch": f"lane/L2-{item_id.lower()}",
        "files_scope": files_scope,
        "depends_on": depends_on,
        "acceptance": ["pytest"],
        "provider_hints": [],
        "status": "READY",
        "lease": None,
    }


def _make_spec(unit: str) -> dict:
    return {
        "adapter": "synthetic",
        "params": {"sleep_s": 0, "write": "out.txt", "content": unit, "hang": False},
        "effect_class": "idempotent",
        "max_attempts": 2,
        "lease_ttl_s": 10,
        "estimated_cost_eur": 0.0,
        "goal_id": "goal.g1.admission",
        "goal_fingerprint": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    }


@pytest.fixture
def g1_queue_env(tmp_path):
    home = tmp_path / "home"
    items_dir = tmp_path / "items"
    ledger_path = tmp_path / "queue_ledger.jsonl"
    home.mkdir(parents=True, exist_ok=True)
    items_dir.mkdir(parents=True, exist_ok=True)
    items = [
        _make_item("WK_BLOCKED_SCOPE", ["courier_worker/queue_feed.py"], []),
        _make_item("WK_UNMET_DEP", ["docs/unmet.md"], ["999"]),
        _make_item("WK_READY_DEP", ["docs/g1_ok.md"], ["281"]),
    ]
    for item in items:
        (items_dir / f"{item['id']}.json").write_text(json.dumps(item), encoding="utf-8")
    config = {
        "items_dir": str(items_dir),
        "ledger": str(ledger_path),
        "holder": HOLDER,
        "ttl_s": 600,
        "admission": {
            "done_prs": ["281"],
            "open_pr_files": ["courier_worker/queue_feed.py"],
            "as_of": "2026-10-24T18:00:00Z",
            "source_sha": "81bbf224b0aeeca4a2b92db29dfc7220b707043a",
        },
        "specs": {
            "WK_BLOCKED_SCOPE": _make_spec("blocked-scope"),
            "WK_UNMET_DEP": _make_spec("unmet-dep"),
            "WK_READY_DEP": _make_spec("ready-dep"),
        },
    }
    (home / "work_queue_feed.json").write_text(json.dumps(config), encoding="utf-8")
    queue = WorkQueue(items_dir=items_dir, ledger_path=ledger_path)
    return {"home": home, "queue": queue, "config_path": home / "work_queue_feed.json"}


def test_g1_admission_passthrough(g1_queue_env):
    home = g1_queue_env["home"]
    queue = g1_queue_env["queue"]
    assert has_open_work(home, now=NOW) is True
    report = feed_once(home, AGENT, HOST, now=NOW)
    assert report["outcome"] == "fed"
    assert report["claimed"] == ["WK_READY_DEP"]
    assert report["assigned"] == ["WK_READY_DEP"]
    by_id = {item["id"]: item for item in queue.items(now=NOW)}
    assert by_id["WK_BLOCKED_SCOPE"]["status"] == "READY"
    assert by_id["WK_UNMET_DEP"]["status"] == "READY"
    assert by_id["WK_READY_DEP"]["status"] == "CLAIMED"
    assert by_id["WK_READY_DEP"]["lease"]["holder"] == HOLDER
