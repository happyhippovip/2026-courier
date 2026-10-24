"""O7-13 (G1): the queue feed drops done_prs / open_pr_files.

courier_core/work_queue.py takes both on list_ready/claim (:71-89, :90-112; CLI
--done-pr / --open-pr-file, :315-327), but courier_worker/queue_feed.py never
passes them: base 81bbf224 :77, :137, :139; WQ-1b v2 (claude/v38-wq1b a2a6dfabd)
:90, :179, :203. Consequences on the automated path:
  * an item whose depends_on names a merged PR is never READY -> never fed;
  * an item whose files_scope overlaps an open PR is claimed anyway (scope collision).
Interface assumed for the fix (owner decides): work_queue_feed.json carries
"done_prs" and "open_pr_files" and the feed hands them to list_ready/claim.
"""
import json

import pytest

from courier_core.work_queue import WorkQueue
from courier_worker import queue_feed

HOLDER = "o7-13-holder"


def _item(item_id, scope, deps=()):
    return {"id": item_id, "title": "Item " + item_id, "lane": "L2", "branch": "lane/L2-" + item_id,
            "files_scope": [scope], "depends_on": list(deps), "acceptance": ["tests"],
            "provider_hints": ["headless"], "status": "READY", "lease": None}


def _home(tmp_path, items, **extra):
    home, items_dir = tmp_path / "home", tmp_path / "items"
    home.mkdir()
    items_dir.mkdir()
    for row in items:
        (items_dir / f"{row['id']}.json").write_text(json.dumps(row), encoding="utf-8")
    ledger = tmp_path / "queue_ledger.jsonl"
    config = {"holder": HOLDER, "items_dir": str(items_dir), "ledger": str(ledger),
              "specs": {row["id"]: {"goal": row["id"]} for row in items}}
    config.update(extra)
    (home / queue_feed.CONFIG_NAME).write_text(json.dumps(config), encoding="utf-8")
    return home, WorkQueue(items_dir=items_dir, ledger_path=ledger)


def test_guard_work_queue_itself_honours_both(tmp_path):
    _home_dir, queue = _home(tmp_path, [_item("WK1", "scope/a.py"), _item("WK2", "scope/b.py", ["PR-123"])])
    ready = [i["id"] for i in queue.list_ready(open_pr_files=["scope/a.py"], done_prs=["PR-123"])]
    assert ready == ["WK2"]


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="O7-13/G1: feed claims an item whose scope overlaps an open PR")
def test_feed_does_not_claim_into_an_open_pr_scope(tmp_path):
    home, _queue = _home(tmp_path, [_item("WK1", "scope/a.py"), _item("WK2", "scope/b.py")],
                         open_pr_files=["scope/a.py"])
    report = queue_feed.feed_once(home, "GOOGLE_WINDOWS", "WINDOWS_REMOTE")
    assert report["claimed"] == ["WK2"], report


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="O7-13/G1: feed never sees merged PRs, so a PR-dependent item is never fed")
def test_feed_feeds_an_item_whose_pr_dependency_is_done(tmp_path):
    home, _queue = _home(tmp_path, [_item("WK2", "scope/b.py", ["PR-123"])], done_prs=["PR-123"])
    report = queue_feed.feed_once(home, "GOOGLE_WINDOWS", "WINDOWS_REMOTE")
    assert report["claimed"] == ["WK2"], report
