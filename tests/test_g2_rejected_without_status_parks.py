"""GOAL-08: a rejected mission with no status is parked, not renewed."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from courier_core.work_queue import WorkQueue
from courier_worker.queue_feed import feed_once

T0 = datetime(2026, 10, 24, 18, 0, 0, tzinfo=timezone.utc)
AGENT = "GOOGLE_MAC"
HOST = "MAC_LOCAL"
HOLDER = "worker-g2"
SOURCE_SHA = "81bbf224b0aeeca4a2b92db29dfc7220b707043a"


def _make_item(item_id: str, files_scope: list[str]) -> dict:
    return {
        "id": item_id,
        "title": f"Task {item_id}",
        "lane": "L2",
        "branch": f"lane/L2-{item_id.lower()}",
        "files_scope": files_scope,
        "depends_on": [],
        "acceptance": ["pytest"],
        "provider_hints": [],
        "status": "READY",
        "lease": None,
    }


def _make_spec(unit: str) -> dict:
    return {
        "adapter": "synthetic",
        "params": {"sleep_s": 0, "write": f"{unit}.txt", "content": unit, "hang": False},
        "effect_class": "idempotent",
        "max_attempts": 2,
        "lease_ttl_s": 10,
        "estimated_cost_eur": 0.0,
        "source_sha": SOURCE_SHA,
        "goal_id": f"goal.g2.{unit}",
        "goal_fingerprint": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    }


@pytest.fixture
def g2_queue_env(tmp_path):
    home = tmp_path / "home"
    items_dir = tmp_path / "items"
    ledger_path = tmp_path / "queue_ledger.jsonl"
    home.mkdir(parents=True, exist_ok=True)
    items_dir.mkdir(parents=True, exist_ok=True)
    for item_id, scope in [("WKA", ["docs/a.md"]), ("WKB", ["docs/b.md"])]:
        (items_dir / f"{item_id}.json").write_text(json.dumps(_make_item(item_id, scope)), encoding="utf-8")
    config = {
        "items_dir": str(items_dir),
        "ledger": str(ledger_path),
        "holder": HOLDER,
        "ttl_s": 600,
        "admission": {
            "done_prs": [],
            "open_pr_files": [],
            "as_of": "2026-10-24T18:00:00Z",
            "source_sha": SOURCE_SHA,
        },
        "specs": {"WKA": _make_spec("wka"), "WKB": _make_spec("wkb")},
    }
    (home / "work_queue_feed.json").write_text(json.dumps(config), encoding="utf-8")
    queue = WorkQueue(items_dir=items_dir, ledger_path=ledger_path)
    return {"home": home, "queue": queue}


def test_g2_rejected_without_status_parks(g2_queue_env):
    home = g2_queue_env["home"]
    queue = g2_queue_env["queue"]
    first = feed_once(home, AGENT, HOST, now=T0)
    assert first["claimed"] == ["WKA"]
    bridge_state = {
        "schema_version": "ledger_bridge_state.v1",
        "missions": {
            "WKA": {
                "task_id": "task-wka-rejected",
                "claim_event_id": "claim-wka-1",
                "idempotency_key": "ledger:claim-wka-1",
                "posted": False,
                "accepted_result_id": None,
                "attempt": None,
            }
        },
    }
    (home / "ledger_bridge_state.json").write_text(json.dumps(bridge_state), encoding="utf-8")
    second = feed_once(home, AGENT, HOST, now=T0 + timedelta(seconds=10))
    assert second["parked"] == ["WKA"]
    assert second["renewed"] == []
    assert second["released"] == []
    assert second["claimed"] == []
    by_id = {item["id"]: item for item in queue.items(now=T0 + timedelta(seconds=10))}
    assert by_id["WKA"]["status"] == "BLOCKED"
    assert by_id["WKA"]["lease"] is None
    assert "BLOCKED" in (by_id["WKA"].get("blocked_reason") or "")
    assert by_id["WKB"]["status"] == "READY"
