"""BLOCKED workkey: one NEEDS_YOU inbox line, then exactly one resume after a
newly confirmed Goal Contract, without a second effect. Synthetic only."""

import json
from collections import Counter

from courier_core.goal_contract import AcceptanceCriterion, Gates, GoalContract, GoalContractStore
from courier_worker import queue_feed
from scripts.coordination_ledger import EventType, MissionStatus
from scripts.coordination_resume import reduce_store
from scripts.github_coordination import FileCoordinationStore
from tests.test_gate4_queue_restart_no_replay import (
    _complete_posted, _queue_seq, _setup, _spec, _tick,
)
from tests.test_ledger_v1_bridge import FakeHTTP


def _contract():
    return GoalContract(
        goal_id="goal-1", end_result="synthetic artifact exists",
        allowed_scope=["out"], forbidden_scope=["secrets"], constraints=["no network"],
        acceptance_criteria=[AcceptanceCriterion("artifact", "out.txt hash matches", "deterministic")],
        side_effect_limits=["no commits"], gates=Gates(human=True, money=True, safety=True))


def _goal_spec(unit, contract):
    spec = _spec(unit)
    spec.update(goal_id=contract.goal_id, goal_fingerprint=contract.fingerprint(),
                goal_task={"scope": ["out"], "acceptance_ids": ["artifact"], "evidence_class": "deterministic"})
    return spec


def _prepare(tmp_path):
    home, queue, ledger = _setup(tmp_path)
    contract = _contract()                      # terms written, not yet confirmed
    GoalContractStore(home / "goal_contracts.jsonl").append(contract)
    config = json.loads((home / queue_feed.CONFIG_NAME).read_text(encoding="utf-8"))
    config["specs"] = {"WKA": _goal_spec("a", contract), "WKB": _goal_spec("b", contract)}
    (home / queue_feed.CONFIG_NAME).write_text(json.dumps(config), encoding="utf-8")
    return home, queue, ledger, contract


def _inbox(home):
    path = home / "run" / queue_feed.NEEDS_YOU_INBOX
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


def _events(home):
    return reduce_store(FileCoordinationStore(home / "coordination_ledger.jsonl")).events


def test_blocked_writes_one_needs_you_then_resumes_once_after_confirmation(tmp_path):
    home, queue, ledger, contract = _prepare(tmp_path)
    http = FakeHTTP()
    for _ in range(4):
        _tick(home, http)
    mission = reduce_store(FileCoordinationStore(home / "coordination_ledger.jsonl")).get_mission("WKA")
    assert mission["status"] == MissionStatus.BLOCKED and "HUMAN_CONFIRMATION_REQUIRED" in mission["blocker"]
    assert http.posts == []
    inbox = _inbox(home)
    assert len(inbox) == 1 and inbox[0]["kind"] == "NEEDS_YOU" and inbox[0]["mission_id"] == "WKA"

    # Human confirms the same terms (appended record). Next ticks: resume once.
    GoalContractStore(home / "goal_contracts.jsonl").append(contract.confirm("person:founder", "2026-10-13T14:00:00Z"))
    for _ in range(12):
        _tick(home, http)
        _complete_posted(http)
        if all(i["status"] == "DONE" for i in queue.items()):
            break
    assert all(i["status"] == "DONE" for i in queue.items()), _queue_seq(ledger)
    events = _events(home)
    resumes = [e for e in events if e.event_id.startswith("queue-resume-")]
    assert len(resumes) == 1 and resumes[0].mission_id == "WKA"
    counts = Counter((e.mission_id, e.event_type) for e in events)
    assert counts["WKA", EventType.FINAL] == 1 and counts["WKB", EventType.FINAL] == 1, counts
    assert counts["WKA", EventType.BLOCKED] == 1, counts
    assert sorted(p["params"]["unit"] for p in http.posts) == ["a", "b"]
    assert _queue_seq(ledger) == [("CLAIM", "WKA"), ("RELEASE", "WKA"), ("CLAIM", "WKB"), ("RELEASE", "WKB")]
    # NEEDS_YOU stays (append-only) and is closed by exactly one RESOLVED line.
    inbox = _inbox(home)
    assert [r["kind"] for r in inbox] == ["NEEDS_YOU", "RESOLVED"], inbox
    assert (inbox[1]["mission_id"], inbox[1]["blocked_event_id"]) == (inbox[0]["mission_id"], inbox[0]["blocked_event_id"])
    assert inbox[1]["resume_event_id"] == resumes[0].event_id

    frozen = ((home / "coordination_ledger.jsonl").read_text(), list(http.posts), _queue_seq(ledger), _inbox(home))
    for _ in range(3):
        _tick(home, http)
    assert ((home / "coordination_ledger.jsonl").read_text(), list(http.posts), _queue_seq(ledger), _inbox(home)) == frozen


def test_unrelated_contract_change_does_not_resume(tmp_path):
    home, queue, ledger, contract = _prepare(tmp_path)
    http = FakeHTTP()
    for _ in range(3):
        _tick(home, http)
    other = GoalContract(**{**{k: getattr(contract, k) for k in (
        "end_result", "allowed_scope", "forbidden_scope", "constraints",
        "acceptance_criteria", "side_effect_limits", "gates")}, "goal_id": "goal-other"})
    GoalContractStore(home / "goal_contracts.jsonl").append(other.confirm("person:founder", "2026-10-13T14:00:00Z"))
    for _ in range(3):
        _tick(home, http)
    assert http.posts == []
    assert not [e for e in _events(home) if e.event_id.startswith("queue-resume-")]
    assert len(_inbox(home)) == 1
