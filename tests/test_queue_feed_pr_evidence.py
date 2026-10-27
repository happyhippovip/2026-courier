"""Feeder passes verified PR evidence into the existing work queue."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from courier_core.work_queue import WorkQueue
from courier_worker.queue_feed import feed_once
from tests.release_proof_helper import FORGED, JournalHome

NOW = datetime(2026, 10, 25, 18, 0, tzinfo=timezone.utc)
AGENT = "GOOGLE_WINDOWS"
HOST = "WINDOWS_REMOTE"
HOLDER = "worker-feeder"


def _item(item_id, scope, depends):
    return {
        "id": item_id,
        "title": item_id,
        "lane": "L2",
        "branch": "lane/L2-" + item_id.lower(),
        "files_scope": scope,
        "depends_on": depends,
        "acceptance": ["pytest"],
        "provider_hints": [],
        "status": "READY",
        "lease": None,
    }


def _home(tmp_path, items, evidence=None):
    home = tmp_path / "home"
    items_dir = tmp_path / "items"
    home.mkdir()
    items_dir.mkdir()
    for item in items:
        (items_dir / f"{item['id']}.json").write_text(json.dumps(item), encoding="utf-8")
    specs = {item["id"]: {"adapter": "synthetic", "params": {"estimated_cost_eur": 0.0}} for item in items}
    (home / "work_queue_feed.json").write_text(json.dumps({
        "items_dir": str(items_dir),
        "ledger": str(tmp_path / "queue.jsonl"),
        "holder": HOLDER,
        "ttl_s": 600,
        "specs": specs,
    }), encoding="utf-8")
    if evidence is not None:
        (home / "pr_evidence.json").write_text(json.dumps(evidence), encoding="utf-8")
    return home, WorkQueue(items_dir=items_dir, ledger_path=tmp_path / "queue.jsonl")


def _fresh(**extra):
    body = {"verified": True, "as_of": NOW.isoformat(), "done_prs": [], "open_pr_files": []}
    body.update(extra)
    return body


def test_verified_done_pr_lets_the_dependent_be_claimed(tmp_path):
    home, queue = _home(tmp_path, [_item("NEXT", ["docs/next.md"], ["277"])],
                        _fresh(done_prs=["277"]))
    report = feed_once(home, AGENT, HOST, now=NOW)
    assert report["claimed"] == ["NEXT"]
    assert queue.items(now=NOW)[0]["status"] == "CLAIMED"


def test_open_pr_281_is_not_treated_as_done(tmp_path):
    home, queue = _home(tmp_path, [_item("REPORT-QA", ["docs/qa.md"], ["281"])],
                        _fresh(done_prs=["281"]))
    report = feed_once(home, AGENT, HOST, now=NOW)
    assert report["claimed"] == []
    assert queue.items(now=NOW)[0]["status"] == "READY"


def test_open_pr_files_block_a_conflicting_claim(tmp_path):
    home, queue = _home(tmp_path, [_item("TOUCH", ["courier_worker/queue_feed.py"], [])],
                        _fresh(open_pr_files=["courier_worker/queue_feed.py"]))
    report = feed_once(home, AGENT, HOST, now=NOW)
    assert report["claimed"] == []
    assert queue.items(now=NOW)[0]["status"] == "READY"


def test_stale_evidence_blocks_and_does_not_release(tmp_path):
    home, queue = _home(tmp_path, [_item("HELD", ["docs/held.md"], [])],
                        _fresh(as_of=(NOW - timedelta(days=2)).isoformat()))
    queue.claim("HELD", HOLDER, 600, host=HOST, now=NOW)
    (home / "ledger_bridge_state.json").write_text(json.dumps({
        "missions": {"HELD": {"status": "FINAL_DONE", "task_id": "task-held",
                              "accepted_result_id": None}}
    }), encoding="utf-8")
    report = feed_once(home, AGENT, HOST, now=NOW)
    assert report["outcome"] == "blocked"
    assert report["released"] == []
    assert queue.items(now=NOW)[0]["status"] == "CLAIMED"


def test_final_done_without_a_result_is_not_released(tmp_path):
    home, queue = _home(tmp_path, [_item("HELD", ["docs/held.md"], [])])
    queue.claim("HELD", HOLDER, 600, host=HOST, now=NOW)
    (home / "ledger_bridge_state.json").write_text(json.dumps({
        "missions": {"HELD": {"status": "FINAL_DONE", "task_id": "task-held",
                              "accepted_result_id": "none"}}
    }), encoding="utf-8")
    report = feed_once(home, AGENT, HOST, now=NOW)
    assert report["outcome"] == "blocked"
    assert report["released"] == []
    assert "HELD" in report["blocked"]


def _journal_claim(home, queue, item_id="HELD"):  # real journal (home/courier.db), then claim + fence
    jh = JournalHome(home, nested=False)
    queue.journal = jh.journal
    queue.claim(item_id, HOLDER, 600, host=HOST, now=NOW)
    return jh


def _final_done(home, **extra):
    mission = {"status": "FINAL_DONE", "task_id": "task-held", "accepted_result_id": "res-accepted-1"}
    mission.update(extra)
    (home / "ledger_bridge_state.json").write_text(json.dumps({"missions": {"HELD": mission}}), encoding="utf-8")


def test_proven_final_done_releases_once_and_restart_does_not_claim_again(tmp_path):
    # P2 R2: FINAL_DONE releases only when the bridge's proof is confirmed by the real journal.
    home, queue = _home(tmp_path, [_item("HELD", ["docs/held.md"], [])])
    jh = _journal_claim(home, queue)
    proof = jh.accept("HELD")
    _final_done(home, journal_proof=proof)
    first = feed_once(home, AGENT, HOST, now=NOW)
    assert first["released"] == ["HELD"]
    again = feed_once(home, AGENT, HOST, now=NOW + timedelta(seconds=5))
    assert again["released"] == []
    assert again["claimed"] == []
    assert queue.items(now=NOW)[0]["status"] == "DONE"
    # Restart: a fresh queue over the same ledger replays to the same single DONE.
    restarted = WorkQueue(items_dir=tmp_path / "items", ledger_path=tmp_path / "queue.jsonl")
    assert [i["status"] for i in restarted.items(now=NOW)] == ["DONE"]
    lines = (tmp_path / "queue.jsonl").read_text(encoding="utf-8").splitlines()
    releases = [json.loads(line) for line in lines if '"RELEASE"' in line]
    assert len(releases) == 1
    assert releases[0]["proof"] == proof


def test_final_done_without_journal_proof_stays_held_and_dispatches_nothing(tmp_path):
    # Negative: FINAL_DONE + accepted_result_id but no journal proof -> no DONE(A), no B.
    home, queue = _home(tmp_path, [_item("HELD", ["docs/held.md"], []),
                                   _item("NEXTB", ["docs/b.md"], ["HELD"])])
    queue.claim("HELD", HOLDER, 600, host=HOST, now=NOW)
    _final_done(home)
    report = feed_once(home, AGENT, HOST, now=NOW)
    assert report["released"] == []
    assert report["not_proven"] == ["HELD"]
    assert "NEXTB" not in report["claimed"]
    status = {i["id"]: i["status"] for i in queue.items(now=NOW)}
    assert status["HELD"] == "CLAIMED"
    assert status["NEXTB"] != "CLAIMED"


def test_fake_journal_proof_is_not_a_release(tmp_path):
    home, queue = _home(tmp_path, [_item("HELD", ["docs/held.md"], [])])
    jh = _journal_claim(home, queue)
    real = jh.accept("HELD")
    foreign = jh.accept("OTHER")       # a real proof of another workkey's task; the mapping even names it
    for fake in FORGED + ("RESULT_ACCEPTED", "journal:0:RESULT_ACCEPTED", "journal:x:RESULT_ACCEPTED",
                          "res-accepted-1", real.split("|")[0], real.split("|")[0] + "|sha256:" + "0" * 64,
                          foreign):
        _final_done(home, journal_proof=fake, task_id=jh.task_id)
        report = feed_once(home, AGENT, HOST, now=NOW)
        assert report["released"] == [] and report["not_proven"] == ["HELD"], fake
        assert queue.items(now=NOW)[0]["status"] == "CLAIMED", fake


def test_without_journal_no_proof_is_a_release(tmp_path):
    # Fail closed: no courier.db in the feed home => nothing is DONE, whatever the mapping says.
    home, queue = _home(tmp_path, [_item("HELD", ["docs/held.md"], [])])
    jh = _journal_claim(tmp_path / "elsewhere", queue)
    for proof in FORGED + (jh.accept("HELD"),):
        _final_done(home, journal_proof=proof)
        report = feed_once(home, AGENT, HOST, now=NOW)
        assert report["released"] == [] and report["not_proven"] == ["HELD"], proof


def test_second_pass_does_not_claim_twice(tmp_path):
    home, _queue = _home(tmp_path, [_item("ONLY", ["docs/only.md"], [])])
    first = feed_once(home, AGENT, HOST, now=NOW)
    second = feed_once(home, AGENT, HOST, now=NOW + timedelta(seconds=5))
    assert first["claimed"] == ["ONLY"]
    assert second["claimed"] == []
    assert second["renewed"] == ["ONLY"]
