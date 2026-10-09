"""Offline tests for the canonical work queue. No network."""

import json
import threading
from datetime import datetime, timedelta, timezone

import jsonschema
import pytest

from courier_core.work_queue import (
    DEFAULT_ITEMS,
    DEFAULT_SCHEMA,
    WorkQueue,
    WorkQueueError,
    main,
)

NOW = datetime(2026, 10, 8, 12, 0, 0, tzinfo=timezone.utc)
READY = ["P2", "P3", "P4", "P6", "P8", "P9"]
TAKEN = ["P1", "P5", "P7"]


def _queue(tmp_path, items=None):
    return WorkQueue(items or DEFAULT_ITEMS, tmp_path / "ledger.jsonl", DEFAULT_SCHEMA)


def _item(item_id, scope, status="READY", depends=None):
    return {
        "id": item_id,
        "title": "Item " + item_id,
        "lane": "L2",
        "branch": "lane/L2-" + item_id,
        "files_scope": scope,
        "depends_on": depends or [],
        "acceptance": ["tests", "draft PR"],
        "provider_hints": ["headless"],
        "status": status,
        "lease": None,
    }


def _write_items(directory, rows):
    directory.mkdir(parents=True, exist_ok=True)
    for row in rows:
        (directory / f"{row['id']}.json").write_text(json.dumps(row), encoding="utf-8")


def test_seed_files_match_schema_and_ready_set():
    schema = json.loads(DEFAULT_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    validator = jsonschema.Draft7Validator(schema)
    ids = []
    for path in sorted(DEFAULT_ITEMS.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        validator.validate(document)
        ids.append(document["id"])
        if document["id"] in TAKEN:
            assert document["status"] == "DONE"
            assert document["lease"] is None
        if document["id"] in READY:
            assert document["status"] == "READY"
            assert document["acceptance"] == ["tests", "draft PR"]
    assert ids == ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9"]


def test_list_ready_skips_taken_items(tmp_path):
    ready = _queue(tmp_path).list_ready(now=NOW)
    assert [item["id"] for item in ready] == READY
    assert all(item["lease"] is None for item in ready)


def test_duplicate_claim_is_rejected_and_same_holder_is_idempotent(tmp_path):
    queue = _queue(tmp_path)
    first = queue.claim("P2", "holder-a", 60, host="local", now=NOW)
    before = (tmp_path / "ledger.jsonl").read_bytes()
    again = queue.claim("P2", "holder-a", 60, host="local", now=NOW + timedelta(seconds=5))
    assert again["idempotent"] is True
    assert again["expires_at"] == first["expires_at"]
    assert (tmp_path / "ledger.jsonl").read_bytes() == before
    with pytest.raises(WorkQueueError) as caught:
        queue.claim("P2", "holder-b", 60, now=NOW)
    assert caught.value.code == "DUPLICATE_CLAIM"
    assert [item["id"] for item in queue.list_ready(now=NOW)] == ["P3", "P4", "P6", "P8", "P9"]


def test_overlapping_scope_is_not_ready_until_the_lease_expires(tmp_path):
    home = tmp_path / "items"
    _write_items(home, [
        _item("A", ["courier_core/*.py"]),
        _item("B", ["courier_core/only_b.py"]),
        _item("C", ["docs/only_c.md"]),
    ])
    queue = WorkQueue(home, tmp_path / "ledger.jsonl")
    assert [item["id"] for item in queue.list_ready(now=NOW)] == ["A", "B", "C"]
    queue.claim("A", "holder-a", 30, now=NOW)
    assert [item["id"] for item in queue.list_ready(now=NOW)] == ["C"]
    with pytest.raises(WorkQueueError) as caught:
        queue.claim("B", "holder-b", 30, now=NOW)
    assert caught.value.code == "SCOPE_OVERLAP"
    later = NOW + timedelta(seconds=31)
    assert [item["id"] for item in queue.list_ready(now=later)] == ["A", "B", "C"]
    claimed = queue.claim("B", "holder-b", 30, now=later)
    assert claimed["holder"] == "holder-b"
    assert claimed["idempotent"] is False


def test_open_pr_files_block_ready_and_claim(tmp_path):
    queue = _queue(tmp_path)
    blocked = queue.list_ready(open_pr_files=["courier_core/result_digest.py"], now=NOW)
    assert "P2" not in [item["id"] for item in blocked]
    assert "P3" in [item["id"] for item in blocked]
    with pytest.raises(WorkQueueError) as caught:
        queue.claim("P2", "holder-a", 60, now=NOW, open_pr_files=["tests/test_result_digest.py"])
    assert caught.value.code == "SCOPE_OVERLAP"


def test_dependencies_on_items_and_prs(tmp_path):
    home = tmp_path / "items"
    _write_items(home, [
        _item("A", ["courier_core/a.py"]),
        _item("B", ["courier_core/b.py"], depends=["A", "277"]),
    ])
    queue = WorkQueue(home, tmp_path / "ledger.jsonl")
    assert [item["id"] for item in queue.list_ready(now=NOW)] == ["A"]
    queue.claim("A", "holder-a", 60, now=NOW)
    queue.release("A", "holder-a", "draft PR", now=NOW)
    assert [item["id"] for item in queue.list_ready(now=NOW)] == []
    ready = queue.list_ready(done_prs=["277"], now=NOW)
    assert [item["id"] for item in ready] == ["B"]
    with pytest.raises(WorkQueueError) as caught:
        queue.claim("B", "holder-b", 60, now=NOW)
    assert caught.value.code == "NOT_CLAIMABLE"
    claimed = queue.claim("B", "holder-b", 60, now=NOW, done_prs=["277"])
    assert claimed["item_id"] == "B"


def test_renew_release_and_replay(tmp_path):
    queue = _queue(tmp_path)
    queue.claim("P4", "holder-a", 60, now=NOW)
    renewed = queue.renew("P4", "holder-a", 120, now=NOW + timedelta(seconds=10))
    assert renewed["expires_at"] == "2026-10-08T12:02:10Z"
    with pytest.raises(WorkQueueError) as caught:
        queue.renew("P4", "holder-b", 60, now=NOW)
    assert caught.value.code == "NOT_HOLDER"
    done = queue.release("P4", "holder-a", "draft PR", now=NOW + timedelta(seconds=11))
    assert done["status"] == "DONE" and done["idempotent"] is False
    before = (tmp_path / "ledger.jsonl").read_bytes()
    again = queue.release("P4", "holder-a", "draft PR", now=NOW)
    assert again["idempotent"] is True
    assert (tmp_path / "ledger.jsonl").read_bytes() == before
    with pytest.raises(WorkQueueError) as caught:
        queue.release("P4", "holder-a", "other result", now=NOW)
    assert caught.value.code == "ALREADY_DONE"
    assert "P4" not in [item["id"] for item in queue.list_ready(now=NOW)]
    with pytest.raises(WorkQueueError) as caught:
        queue.claim("P1", "holder-a", 60, now=NOW)
    assert caught.value.code == "NOT_CLAIMABLE"


def test_expired_renew_is_rejected(tmp_path):
    queue = _queue(tmp_path)
    queue.claim("P6", "holder-a", 10, now=NOW)
    with pytest.raises(WorkQueueError) as caught:
        queue.renew("P6", "holder-a", 10, now=NOW + timedelta(seconds=11))
    assert caught.value.code == "NOT_HOLDER"


def test_malformed_catalog_and_ledger_fail_closed(tmp_path):
    home = tmp_path / "items"
    _write_items(home, [_item("A", ["courier_core/a.py"])])
    (home / "A.json").write_text("{", encoding="utf-8")
    with pytest.raises(WorkQueueError) as caught:
        WorkQueue(home, tmp_path / "ledger.jsonl").list_ready(now=NOW)
    assert caught.value.code == "UNREADABLE"
    home2 = tmp_path / "items2"
    _write_items(home2, [_item("A", ["courier_core/a.py"]) | {"extra": 1}])
    with pytest.raises(WorkQueueError) as caught:
        WorkQueue(home2, tmp_path / "ledger2.jsonl").list_ready(now=NOW)
    assert caught.value.code == "INVALID_ITEM"
    ledger = tmp_path / "bad.jsonl"
    _write_items(tmp_path / "ok", [_item("A", ["courier_core/a.py"])])
    ledger.write_text("{}\n", encoding="utf-8")
    with pytest.raises(WorkQueueError) as caught:
        WorkQueue(tmp_path / "ok", ledger).list_ready(now=NOW)
    assert caught.value.code == "UNREADABLE"


def test_blocked_seed_is_not_ready(tmp_path):
    home = tmp_path / "items"
    _write_items(home, [_item("A", ["courier_core/a.py"], status="BLOCKED")])
    queue = WorkQueue(home, tmp_path / "ledger.jsonl")
    assert queue.list_ready(now=NOW) == []
    with pytest.raises(WorkQueueError) as caught:
        queue.claim("A", "holder-a", 30, now=NOW)
    assert caught.value.code == "NOT_CLAIMABLE"


def test_concurrent_claims_one_winner(tmp_path):
    queue_path = tmp_path / "ledger.jsonl"
    barrier = threading.Barrier(2)
    outcomes = []

    def attempt(holder):
        barrier.wait()
        try:
            view = WorkQueue(DEFAULT_ITEMS, queue_path).claim("P8", holder, 60, now=NOW)
            outcomes.append((holder, view["status"]))
        except WorkQueueError as exc:
            outcomes.append((holder, exc.code))

    threads = [threading.Thread(target=attempt, args=(name,)) for name in ("holder-a", "holder-b")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(code for _holder, code in outcomes) == ["CLAIMED", "DUPLICATE_CLAIM"]


def test_cli_next_prints_prompt_without_claiming(tmp_path, capsys):
    ledger = tmp_path / "ledger.jsonl"
    assert main(["--ledger", str(ledger), "next", "--holder", "window-a"]) == 0
    text = capsys.readouterr().out
    assert "id: P2" in text
    assert "lane/L2-result-digest-P2" in text
    assert "draft PR" in text
    assert "Claim the item before writing" in text
    assert not ledger.exists()
    assert main(["--ledger", str(ledger), "claim", "--item", "P2", "--holder", "window-a", "--ttl", "60"]) == 0
    assert "CLAIMED" in capsys.readouterr().out
    assert main(["--ledger", str(ledger), "next", "--holder", "window-b"]) == 0
    assert "id: P2" not in capsys.readouterr().out
    assert main(["--ledger", str(ledger), "release", "--item", "P2", "--holder", "other", "--result", "draft PR"]) == 2
    assert capsys.readouterr().err.strip() == "NOT_HOLDER"


def test_cli_next_empty(tmp_path, capsys):
    home = tmp_path / "items"
    _write_items(home, [_item("A", ["courier_core/a.py"], status="DONE")])
    code = main(["--items", str(home), "--ledger", str(tmp_path / "ledger.jsonl"), "next", "--holder", "window-a"])
    assert code == 0
    assert capsys.readouterr().out.strip() == "NO_READY_ITEM"
