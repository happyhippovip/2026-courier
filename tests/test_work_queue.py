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
CLAIMED = {
    "P2": "287",
    "P3": "298",
    "P4": "301",
    "P6": "304",
    "P8": "309",
    "WK7": "305",
}
DONE = ["P1", "P5", "P7"]


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


def test_seed_files_match_schema_and_claims(tmp_path):
    schema = json.loads(DEFAULT_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    validator = jsonschema.Draft7Validator(schema)
    ids = []
    for path in sorted(DEFAULT_ITEMS.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        validator.validate(document)
        ids.append(document["id"])
        assert "draft PR" in document["acceptance"]
        if document["id"] in DONE:
            assert document["status"] == "DONE"
            assert document["lease"] is None
        if document["id"] in CLAIMED:
            assert document["status"] == "CLAIMED"
            assert document["pull_request"] == CLAIMED[document["id"]]
            assert document["lease"]["expires_at"] is None
    assert ids == ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "REPORT-QA", "WK7"]
    queue = WorkQueue(DEFAULT_ITEMS, tmp_path / "ledger.jsonl", DEFAULT_SCHEMA)
    by_id = {item["id"]: item for item in queue.items(now=NOW)}
    assert by_id["P2"]["publish_gate"] == "explicit_human_approval"
    assert by_id["P2"]["files_scope"] == [
        "missions/templates/short_video.json",
        "courier_core/short_video.py",
        "tests/test_short_video.py",
    ]
    assert by_id["P3"]["provider_hints"] == ["no network", "no credentials", "visibility private"]
    assert by_id["P3"]["files_scope"] == ["courier_worker/publish/youtube_dryrun.py"]
    assert by_id["P4"]["provider_hints"] == ["no network", "no credentials", "inbox-draft only"]
    assert by_id["P4"]["files_scope"] == ["courier_worker/publish/tiktok_dryrun.py"]
    assert by_id["P6"]["files_scope"] == ["courier_core/worker_tokens.py"]
    assert by_id["P6"]["title"] == "worker tokens"
    assert by_id["WK7"]["lease"]["holder"] == "cloud:lane/L3-local-veto"
    assert by_id["WK7"]["branch"] == "lane/L3-local-veto"
    assert "adapters/local_shell.py" not in by_id["WK7"]["files_scope"]
    assert by_id["P8"]["depends_on"] == ["272"]
    assert by_id["P8"]["status"] == "CLAIMED"
    assert by_id["P8"]["lane"] == "L5"
    assert by_id["P8"]["branch"] == "lane/L5-hub-mission-list-P8"
    assert by_id["P8"]["files_scope"] == ["courier_hub/server.py", "tests/hub/test_hub_mission_list.py"]
    assert "stack on lane/L2-receipt-read-model" in by_id["P8"]["acceptance"]
    assert by_id["REPORT-QA"]["depends_on"] == ["281"]
    assert by_id["REPORT-QA"]["files_scope"] == ["tests/"]
    assert by_id["P9"]["template"] is True
    assert by_id["P9"]["files_scope"] == ["tests/"]


def test_list_ready_skips_taken_items(tmp_path):
    queue = _queue(tmp_path)
    assert queue.list_ready(now=NOW) == []
    assert queue.list_ready(now=NOW.replace(year=2099)) == []
    ready = queue.list_ready(done_prs=["281"], now=NOW)
    assert [item["id"] for item in ready] == ["REPORT-QA"]
    assert "P8" not in [item["id"] for item in ready]
    assert "P9" not in [item["id"] for item in ready]


def test_duplicate_claim_is_rejected_and_same_holder_is_idempotent(tmp_path):
    queue = _queue(tmp_path)
    first = queue.claim("REPORT-QA", "holder-a", 60, host="local", now=NOW, done_prs=["281"])
    before = (tmp_path / "ledger.jsonl").read_bytes()
    again = queue.claim("REPORT-QA", "holder-a", 60, host="local", now=NOW + timedelta(seconds=5), done_prs=["281"])
    assert again["idempotent"] is True
    assert again["expires_at"] == first["expires_at"]
    assert (tmp_path / "ledger.jsonl").read_bytes() == before
    with pytest.raises(WorkQueueError) as caught:
        queue.claim("REPORT-QA", "holder-b", 60, now=NOW, done_prs=["281"])
    assert caught.value.code == "DUPLICATE_CLAIM"
    taken = queue.claim("P2", "pr:287", 60, now=NOW)
    assert taken["idempotent"] is True
    assert taken["holder"] == "pr:287"
    with pytest.raises(WorkQueueError) as caught:
        queue.claim("P2", "holder-b", 60, now=NOW)
    assert caught.value.code == "DUPLICATE_CLAIM"
    with pytest.raises(WorkQueueError) as caught:
        queue.renew("WK7", "cloud:lane/L3-local-veto", 60, now=NOW)
    assert caught.value.code == "NOT_RENEWABLE"


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
    blocked = queue.list_ready(open_pr_files=["tests/"], done_prs=["281"], now=NOW)
    assert blocked == []
    with pytest.raises(WorkQueueError) as caught:
        queue.claim("REPORT-QA", "holder-a", 60, now=NOW, done_prs=["281"], open_pr_files=["tests/"])
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
    queue.claim("REPORT-QA", "holder-a", 60, now=NOW, done_prs=["281"])
    renewed = queue.renew("REPORT-QA", "holder-a", 120, now=NOW + timedelta(seconds=10))
    assert renewed["expires_at"] == "2026-10-08T12:02:10Z"
    with pytest.raises(WorkQueueError) as caught:
        queue.renew("REPORT-QA", "holder-b", 60, now=NOW)
    assert caught.value.code == "NOT_HOLDER"
    done = queue.release("REPORT-QA", "holder-a", "draft PR", now=NOW + timedelta(seconds=11))
    assert done["status"] == "DONE" and done["idempotent"] is False
    before = (tmp_path / "ledger.jsonl").read_bytes()
    again = queue.release("REPORT-QA", "holder-a", "draft PR", now=NOW)
    assert again["idempotent"] is True
    assert (tmp_path / "ledger.jsonl").read_bytes() == before
    with pytest.raises(WorkQueueError) as caught:
        queue.release("REPORT-QA", "holder-a", "other result", now=NOW)
    assert caught.value.code == "ALREADY_DONE"
    assert "REPORT-QA" not in [item["id"] for item in queue.list_ready(done_prs=["281"], now=NOW)]
    with pytest.raises(WorkQueueError) as caught:
        queue.claim("P1", "holder-a", 60, now=NOW)
    assert caught.value.code == "NOT_CLAIMABLE"
    with pytest.raises(WorkQueueError) as caught:
        queue.claim("P9", "holder-a", 60, now=NOW)
    assert caught.value.code == "NOT_CLAIMABLE"


def test_expired_renew_is_rejected(tmp_path):
    queue = _queue(tmp_path)
    queue.claim("REPORT-QA", "holder-a", 10, now=NOW, done_prs=["281"])
    with pytest.raises(WorkQueueError) as caught:
        queue.renew("REPORT-QA", "holder-a", 10, now=NOW + timedelta(seconds=11))
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
            view = WorkQueue(DEFAULT_ITEMS, queue_path).claim("REPORT-QA", holder, 60, now=NOW, done_prs=["281"])
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
    assert capsys.readouterr().out.strip() == "NO_READY_ITEM"
    assert not ledger.exists()
    assert main(["--ledger", str(ledger), "next", "--holder", "window-a", "--done-pr", "281"]) == 0
    text = capsys.readouterr().out
    assert "id: REPORT-QA" in text
    assert "lane/L4-report-qa" in text
    assert "tests only" in text
    assert "draft PR" in text
    assert "Claim the item before writing" in text
    assert not ledger.exists()
    assert main(["--ledger", str(ledger), "claim", "--item", "REPORT-QA", "--holder", "window-a", "--ttl", "60", "--done-pr", "281"]) == 0
    assert "CLAIMED" in capsys.readouterr().out
    assert main(["--ledger", str(ledger), "next", "--holder", "window-b", "--done-pr", "281"]) == 0
    assert "id: REPORT-QA" not in capsys.readouterr().out
    assert main(["--ledger", str(ledger), "release", "--item", "REPORT-QA", "--holder", "other", "--result", "draft PR"]) == 2
    assert capsys.readouterr().err.strip() == "NOT_HOLDER"


def test_p9_template_spawns_claim_once_items(tmp_path):
    queue = _queue(tmp_path)
    first = queue.spawn("P9", "worker_tokens", now=NOW)
    assert first["item_id"] == "P9-worker_tokens"
    assert first["files_scope"] == ["tests/"]
    assert first["claim_once"] is True
    assert first["idempotent"] is False
    before = (tmp_path / "ledger.jsonl").read_bytes()
    again = queue.spawn("P9", "worker_tokens", now=NOW)
    assert again["idempotent"] is True
    assert (tmp_path / "ledger.jsonl").read_bytes() == before
    other = queue.spawn("P9", "media_verify", now=NOW)
    assert other["item_id"] == "P9-media_verify"
    assert [item["id"] for item in queue.list_ready(now=NOW)] == ["P9-media_verify", "P9-worker_tokens"]
    queue.claim("P9-worker_tokens", "holder-a", 30, now=NOW)
    assert [item["id"] for item in queue.list_ready(now=NOW)] == []
    with pytest.raises(WorkQueueError) as caught:
        queue.claim("P9-media_verify", "holder-b", 30, now=NOW)
    assert caught.value.code == "SCOPE_OVERLAP"
    later = NOW + timedelta(seconds=31)
    assert [item["id"] for item in queue.list_ready(now=later)] == ["P9-media_verify"]
    with pytest.raises(WorkQueueError) as caught:
        queue.claim("P9-worker_tokens", "holder-b", 30, now=later)
    assert caught.value.code == "NOT_CLAIMABLE"
    with pytest.raises(WorkQueueError) as caught:
        queue.spawn("P9", "../secrets", now=NOW)
    assert caught.value.code == "INVALID_MODULE"
    assert main(["--ledger", str(tmp_path / "ledger.jsonl"), "--items", str(DEFAULT_ITEMS), "spawn", "--template", "P9", "--module", "worker_tokens"]) == 0


def test_external_claim_ignores_the_clock(tmp_path):
    home = tmp_path / "items"
    row = _item("A", ["courier_core/a.py"], status="CLAIMED")
    row["pull_request"] = "287"
    row["lease"] = {"holder": "pr:287", "host": "local", "expires_at": "2020-01-01T00:00:00Z"}
    _write_items(home, [row])
    queue = WorkQueue(home, tmp_path / "ledger.jsonl")
    assert queue.list_ready(now=NOW) == []
    with pytest.raises(WorkQueueError) as caught:
        queue.claim("A", "other", 60, now=NOW)
    assert caught.value.code == "DUPLICATE_CLAIM"


def test_cli_next_empty(tmp_path, capsys):
    home = tmp_path / "items"
    _write_items(home, [_item("A", ["courier_core/a.py"], status="DONE")])
    code = main(["--items", str(home), "--ledger", str(tmp_path / "ledger.jsonl"), "next", "--holder", "window-a"])
    assert code == 0
    assert capsys.readouterr().out.strip() == "NO_READY_ITEM"
