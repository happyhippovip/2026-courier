"""Feeder passes verified PR evidence into the existing work queue."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from courier_core.work_queue import WorkQueue
from courier_worker.queue_feed import feed_once
from scripts.coordination_ledger import AgentID, CoordinationEvent, EventType, HostID, MissionStatus
from scripts.github_coordination import FileCoordinationStore
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
    queue.journal = (jh := JournalHome(home, nested=False)).journal
    queue.claim(item_id, HOLDER, 600, host=HOST, now=NOW)
    return jh


def _final_done(home, **extra):
    mission = {"status": "FINAL_DONE", "task_id": "task-held", "accepted_result_id": "res-accepted-1", **extra}
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
    restarted = WorkQueue(items_dir=tmp_path / "items", ledger_path=tmp_path / "queue.jsonl")  # restart: same DONE
    assert [i["status"] for i in restarted.items(now=NOW)] == ["DONE"]
    lines = (tmp_path / "queue.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["proof"] for line in lines if '"RELEASE"' in line] == [proof]  # exactly one RELEASE


def test_second_pass_does_not_claim_twice(tmp_path):
    home, _queue = _home(tmp_path, [_item("ONLY", ["docs/only.md"], [])])
    first = feed_once(home, AGENT, HOST, now=NOW)
    second = feed_once(home, AGENT, HOST, now=NOW + timedelta(seconds=5))
    assert first["claimed"] == ["ONLY"]
    assert second["claimed"] == []
    assert second["renewed"] == ["ONLY"]


def test_without_journal_no_proof_is_a_release(tmp_path):
    # FINAL_DONE without journal proof, or without courier.db in the feed home (fail closed): no DONE(A), no B.
    home, queue = _home(tmp_path, [_item("HELD", ["docs/held.md"], []),
                                   _item("NEXTB", ["docs/b.md"], ["HELD"])])
    jh = _journal_claim(tmp_path / "elsewhere", queue)
    for proof in (None,) + FORGED + (jh.accept("HELD"),):
        _final_done(home, **({} if proof is None else {"journal_proof": proof}))
        report = feed_once(home, AGENT, HOST, now=NOW)
        assert (report["released"], report["not_proven"], "NEXTB" in report["claimed"]) == ([], ["HELD"], False), proof
        assert [(i["id"], i["status"] == "CLAIMED") for i in queue.items(now=NOW)] == [("HELD", True), ("NEXTB", False)]


def test_fake_or_foreign_mission_proof_is_not_a_release(tmp_path):
    # X07/X06: only "claim-" events of this mission name bridge tasks (key ledger:<claim event id>). Real proofs
    # of another workkey's task (the mapping even names it), of another mission or without a claim event: no release.
    home, queue = _home(tmp_path, [_item("HELD", ["docs/held.md"], [])])
    jh = _journal_claim(home, queue)
    store = FileCoordinationStore(home / "coordination_ledger.jsonl")
    for event_id, mission in (("claim-other-y", "OTHER"), ("queue-assign-HELD", "HELD"), ("claim-held-x", "HELD")):
        store.write_event(CoordinationEvent(
            event_id=event_id, mission_id=mission, agent_id=AgentID(AGENT), host_id=HostID(HOST),
            event_type=EventType.ASSIGNED, status=MissionStatus.WORKING, depends_on=[], head="work_queue",
            evidence_ref=f"work_queue:{mission}", created_at=NOW.isoformat().replace("+00:00", "Z"),
            payload_hash="work_queue", ownership=AGENT))
    real = jh.accept("HELD")
    named = [(jh.accept(wk, key=key), jh.task_id) for wk, key in (
        ("OTHER", None), ("HELD", "ledger:claim-other-y"), ("HELD", "ledger:queue-assign-HELD"))]
    for fake, task in [(f, named[0][1]) for f in FORGED + (
            "RESULT_ACCEPTED", "journal:0:RESULT_ACCEPTED", "journal:x:RESULT_ACCEPTED", "res-accepted-1",
            real.split("|")[0], real.split("|")[0] + "|sha256:" + "0" * 64)] + named:
        _final_done(home, journal_proof=fake, task_id=task)
        report = feed_once(home, AGENT, HOST, now=NOW)
        assert report["released"] == [] and report["not_proven"] == ["HELD"], fake
        assert queue.items(now=NOW)[0]["status"] == "CLAIMED", fake
    _final_done(home, journal_proof=jh.accept("HELD", key="ledger:claim-held-x"), task_id=jh.task_id)
    assert feed_once(home, AGENT, HOST, now=NOW)["released"] == ["HELD"]
