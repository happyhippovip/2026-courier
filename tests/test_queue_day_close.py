"""Day close on the queue feed: bound known issues, name the next owner, idle only when empty.

The feed is the ledger motor link (queue claim -> ASSIGNED -> release). These
cases stay on synthetic files. They do not start a controller.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from courier_worker import queue_feed
from courier_worker.queue_feed import feed_once

NOW = datetime(2026, 10, 13, 15, 0, 0, tzinfo=timezone.utc)
AGENT = "GOOGLE_WINDOWS"
HOST = "WINDOWS_REMOTE"
HOLDER = "worker-dayclose"


def _item(item_id, status="READY", depends=None):
    return {
        "id": item_id,
        "title": "Item " + item_id,
        "lane": "L2",
        "branch": "lane/L2-" + item_id,
        "files_scope": ["out/" + item_id + "/"],
        "depends_on": depends or [],
        "acceptance": ["synthetic artifact"],
        "provider_hints": [],
        "status": status,
        "lease": None,
    }


def _setup(tmp_path: Path, rows, specs):
    home = tmp_path / "home"
    items = tmp_path / "items"
    home.mkdir()
    items.mkdir()
    for row in rows:
        (items / f"{row['id']}.json").write_text(json.dumps(row), encoding="utf-8")
    ledger = tmp_path / "queue.jsonl"
    (home / "work_queue_feed.json").write_text(json.dumps({
        "items_dir": str(items),
        "ledger": str(ledger),
        "holder": HOLDER,
        "ttl_s": 600,
        "specs": specs,
    }), encoding="utf-8")
    return home, ledger


def _spec(unit):
    return {"adapter": "synthetic", "params": {"content": unit}}


def _events(ledger: Path):
    if not ledger.exists():
        return []
    return [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line]


def test_renewed_hold_is_not_global_idle(tmp_path):
    home, ledger = _setup(tmp_path, [_item("W")], {"W": _spec("w")})
    first = feed_once(home, AGENT, HOST, now=NOW)
    assert first["claimed"] == ["W"]
    second = feed_once(home, AGENT, HOST, now=NOW)
    assert second["renewed"] == ["W"]
    assert second["claimed"] == []
    assert second["outcome"] == "held"
    assert second["outcome"] != "idle"
    assert [e for e in _events(ledger) if e["type"] == "CLAIM"] == [e for e in _events(ledger) if e["type"] == "CLAIM"][:1]
    assert len([e for e in _events(ledger) if e["type"] == "CLAIM"]) == 1


def test_ready_work_outside_specs_is_not_idle(tmp_path):
    home, _ledger = _setup(tmp_path, [_item("W")], {})
    report = feed_once(home, AGENT, HOST, now=NOW)
    assert report["claimed"] == []
    assert report["outcome"] == "ready"
    assert report["outcome"] != "idle"


def test_known_issues_over_cap_are_refused_and_not_claimed(tmp_path):
    rows = [_item(f"K{i}", status="BLOCKED") for i in range(queue_feed.MAX_KNOWN_ISSUES + 1)]
    rows.append(_item("W"))
    home, ledger = _setup(tmp_path, rows, {"W": _spec("w")})
    report = feed_once(home, AGENT, HOST, now=NOW)
    assert report["claimed"] == []
    assert report["outcome"] == "known_issues"
    assert report["known_issues"] == []
    assert report["outcome"] != "idle"
    assert _events(ledger) == []
    assert feed_once(home, AGENT, HOST, now=NOW) == report
    assert len(rows) - 1 > queue_feed.MAX_KNOWN_ISSUES


def test_known_issue_within_cap_is_listed_and_work_still_moves(tmp_path):
    home, _ledger = _setup(
        tmp_path,
        [_item("K1", status="BLOCKED"), _item("W")],
        {"W": _spec("w")},
    )
    report = feed_once(home, AGENT, HOST, now=NOW)
    assert report["claimed"] == ["W"]
    assert report["outcome"] == "fed"
    assert report["known_issues"] == ["K1"]
    assert report["next_owner"] == HOLDER
    second = feed_once(home, AGENT, HOST, now=NOW)
    assert second["known_issues"] == ["K1"]
    assert second["outcome"] == "held"
    assert second["claimed"] == []


def test_next_owner_mismatch_is_refused():
    refused = queue_feed.next_owner_handoff(
        {"claimed": ["W"], "released": [], "next_owner": "other"},
        HOLDER,
    )
    assert refused == "owner_mismatch"
    invented = queue_feed.next_owner_handoff(
        {"claimed": [], "released": ["W"], "next_owner": HOLDER},
        HOLDER,
    )
    assert invented == "owner_without_claim"
    missing = queue_feed.next_owner_handoff({"claimed": [], "next_owner": None}, "  ")
    assert missing == "missing_holder"


def test_idle_only_when_nothing_is_left_and_the_reading_stays(tmp_path):
    home, ledger = _setup(tmp_path, [_item("W")], {"W": _spec("w")})
    claimed = feed_once(home, AGENT, HOST, now=NOW)
    assert claimed["next_owner"] == HOLDER
    assert queue_feed.next_owner_handoff(claimed, HOLDER) == "accepted"
    (home / "ledger_bridge_state.json").write_text(json.dumps({
        "missions": {"W": {"status": "FINAL_DONE", "task_id": "t-w"}},
    }), encoding="utf-8")
    released = feed_once(home, AGENT, HOST, now=NOW)
    assert released["released"] == ["W"]
    assert released["claimed"] == []
    assert released["next_owner"] is None
    assert queue_feed.next_owner_handoff(released, HOLDER) == "no_handoff"
    idle = feed_once(home, AGENT, HOST, now=NOW)
    again = feed_once(home, AGENT, HOST, now=NOW)
    assert idle["outcome"] == "idle"
    assert idle == again
    assert [e["type"] for e in _events(ledger)] == ["CLAIM", "RELEASE"]
