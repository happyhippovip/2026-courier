"""Catalog 2801-2825: read PR 491, block draft PR 495, name shared paths.

Offline fixtures from the PR records already read. No network and no merge.
"""
import json
from datetime import datetime, timezone

import pytest

from courier_core.work_queue import DEFAULT_SCHEMA, WorkQueue, WorkQueueError

NOW = datetime(2026, 10, 13, 15, 0, 0, tzinfo=timezone.utc)
PR_491 = {
    "number": "491",
    "state": "MERGED",
    "is_draft": False,
    "files": [
        "scripts/run_antigravity_bridge.py",
        "tests/test_run_antigravity_bridge.py",
    ],
}
PR_495 = {
    "number": "495",
    "state": "OPEN",
    "is_draft": True,
    "files": ["tests/test_worker_host_spawn_contained.py"],
}


def _readers():
    from courier_core.work_queue import (
        draft_gate,
        read_pr_dependency,
        shared_file_conflicts,
    )

    return read_pr_dependency, draft_gate, shared_file_conflicts


def _item(item_id, scope, depends=None):
    return {
        "id": item_id,
        "title": "Item " + item_id,
        "lane": "L2",
        "branch": "lane/L2-" + item_id,
        "files_scope": scope,
        "depends_on": depends or [],
        "acceptance": ["tests", "draft PR"],
        "provider_hints": ["headless"],
        "status": "READY",
        "lease": None,
    }


def _queue(tmp_path, rows):
    home = tmp_path / "items"
    home.mkdir()
    for row in rows:
        (home / f"{row['id']}.json").write_text(json.dumps(row), encoding="utf-8")
    return WorkQueue(home, tmp_path / "ledger.jsonl", DEFAULT_SCHEMA)


def test_file_under_tests_scope_is_a_conflict(tmp_path):
    queue = _queue(tmp_path, [_item("REPORT-QA", ["tests/"], depends=["281"])])
    ready = queue.list_ready(
        open_pr_files=["tests/test_worker_host_spawn_contained.py"],
        done_prs=["281"],
        now=NOW,
    )
    assert ready == []
    with pytest.raises(WorkQueueError) as caught:
        queue.claim(
            "REPORT-QA",
            "holder-a",
            60,
            now=NOW,
            done_prs=["281"],
            open_pr_files=["tests/test_worker_host_spawn_contained.py"],
        )
    assert caught.value.code == "SCOPE_OVERLAP"


def test_merged_491_is_a_dependency_and_not_a_second_merge():
    read_pr_dependency, _, _ = _readers()
    record = read_pr_dependency(PR_491)
    assert record["number"] == "491"
    assert record["role"] == "MERGED_DEPENDENCY"
    assert record["merge_again"] is False
    assert record["ready"] is False
    assert record["files"] == PR_491["files"]
    assert read_pr_dependency(PR_491) == record


def test_draft_495_is_blocked_and_a_clear_draft_flag_is_still_not_ready():
    _, draft_gate, _ = _readers()
    blocked = draft_gate(PR_495)
    assert blocked["role"] == "DRAFT_BLOCKED"
    assert blocked["draft_gate"] == "BLOCKED"
    assert blocked["ready"] is False
    assert blocked["merge_again"] is False
    opened = draft_gate({**PR_495, "is_draft": False})
    assert opened["draft_gate"] == "CLEAR"
    assert opened["ready"] is False
    assert draft_gate(PR_491)["draft_gate"] == "NOT_APPLICABLE"


def test_dependency_reader_rejects_a_missing_flag_and_a_draft_merge():
    read_pr_dependency, _, _ = _readers()
    bare = dict(PR_491)
    del bare["is_draft"]
    with pytest.raises(WorkQueueError) as missing:
        read_pr_dependency(bare)
    assert missing.value.code == "DRAFT_FLAG_REQUIRED"
    with pytest.raises(WorkQueueError) as both:
        read_pr_dependency({**PR_491, "is_draft": True})
    assert both.value.code == "DRAFT_MERGED"


def test_491_and_495_share_no_path_and_a_bridge_edit_does():
    _, _, shared_file_conflicts = _readers()
    assert shared_file_conflicts([PR_491, PR_495]) == []
    conflicts = shared_file_conflicts([
        PR_491,
        PR_495,
        {"number": "900", "files": ["scripts/run_antigravity_bridge.py"]},
    ])
    assert conflicts == [{
        "left": "491",
        "right": "900",
        "paths": ["scripts/run_antigravity_bridge.py"],
    }]
    again = shared_file_conflicts([
        PR_491,
        PR_495,
        {"number": "900", "files": ["scripts/run_antigravity_bridge.py"]},
    ])
    assert again == conflicts


def test_directory_scope_conflicts_with_the_495_file():
    _, _, shared_file_conflicts = _readers()
    conflicts = shared_file_conflicts([
        PR_495,
        {"number": "P9", "files": ["tests/"]},
    ])
    assert conflicts == [{
        "left": "495",
        "right": "P9",
        "paths": ["tests/ ~ tests/test_worker_host_spawn_contained.py"],
    }]


def test_draft_number_does_not_satisfy_depends_on(tmp_path):
    queue = _queue(tmp_path, [_item("CHILD", ["docs/only.md"], depends=["495"])])
    assert queue.list_ready(done_prs=["495"], draft_prs=["495"], now=NOW) == []
    with pytest.raises(WorkQueueError) as caught:
        queue.claim("CHILD", "holder-a", 60, now=NOW, done_prs=["495"], draft_prs=["495"])
    assert caught.value.code == "NOT_CLAIMABLE"


def test_merged_491_still_satisfies_depends_on_when_it_is_not_draft(tmp_path):
    queue = _queue(tmp_path, [_item("CHILD", ["docs/only.md"], depends=["491"])])
    ready = queue.list_ready(done_prs=["491"], draft_prs=[], now=NOW)
    assert [item["id"] for item in ready] == ["CHILD"]
    claimed = queue.claim("CHILD", "holder-a", 60, now=NOW, done_prs=["491"], draft_prs=[])
    assert claimed["holder"] == "holder-a"


def test_draft_mark_wins_over_the_same_number_in_done(tmp_path):
    queue = _queue(tmp_path, [_item("CHILD", ["docs/only.md"], depends=["491"])])
    assert queue.list_ready(done_prs=["491"], draft_prs=["491"], now=NOW) == []
