"""Bridge dispatch checks the Goal Contract (courier_core.goal_contract, #268).

Valid confirmed contract -> posted once. Stale fingerprint, unconfirmed,
widened scope, missing contract -> BLOCKED before claim/post, no side effect,
replay is a no-op. Without goal_contracts.jsonl behaviour is unchanged.
"""

import hashlib

from courier_core.goal_contract import AcceptanceCriterion, Gates, GoalContract, GoalContractStore
from scripts.coordination_ledger import EventType, MissionStatus
from scripts.coordination_resume import reduce_store
from scripts.github_coordination import FileCoordinationStore
from tests.test_ledger_v1_bridge import FakeHTTP, _home, _ready, _run, _seed, _spec


def _contract(**overrides):
    values = dict(
        goal_id="goal-1", end_result="synthetic artifact exists",
        allowed_scope=["out"], forbidden_scope=["secrets"], constraints=["no network"],
        acceptance_criteria=[AcceptanceCriterion("artifact", "out.txt hash matches", "deterministic")],
        side_effect_limits=["no commits"], gates=Gates(human=True, money=True, safety=True),
    )
    values.update(overrides)
    return GoalContract(**values)


def _goal_spec(contract, fingerprint=None, **task):
    view = {"scope": ["out"], "acceptance_ids": ["artifact"], "evidence_class": "deterministic"}
    view.update(task)
    return _spec(goal_id=contract.goal_id, goal_fingerprint=fingerprint or contract.fingerprint(), goal_task=view)


def _setup(tmp_path, spec, contracts):
    home = _home(tmp_path, {"A": spec})
    store = GoalContractStore(home / "goal_contracts.jsonl")
    for contract in contracts:
        store.append(contract)
    _seed(home, [_ready("A", "a-assign")])
    return home


def _reducer(home):
    return reduce_store(FileCoordinationStore(home / "coordination_ledger.jsonl"))


def _assert_blocked_without_effect(home, http, word):
    assert http.posts == []
    reducer = _reducer(home)
    mission = reducer.get_mission("A")
    assert mission["status"] == MissionStatus.BLOCKED
    assert "goal_contract" in mission["blocker"] and word in mission["blocker"], mission["blocker"]
    types = [e.event_type for e in reducer.events]
    assert types.count(EventType.BLOCKED) == 1
    assert EventType.STARTED not in types and EventType.FINAL not in types
    assert not (home / "ledger_bridge_state.json").exists() or '"A"' not in (home / "ledger_bridge_state.json").read_text()
    before = (home / "coordination_ledger.jsonl").read_text(encoding="utf-8")
    assert _run(home, http)[0] == 0
    assert http.posts == []
    assert (home / "coordination_ledger.jsonl").read_text(encoding="utf-8") == before


def test_confirmed_contract_posts_once_and_replay_is_noop(tmp_path):
    contract = _contract().confirm("person:founder", "2026-10-13T12:00:00Z")
    home = _setup(tmp_path, _goal_spec(contract), [contract])
    http = FakeHTTP()
    code, out, err, log, lines = _run(home, http)
    assert code == 0, err
    assert len(http.posts) == 1
    assert "goal_task" not in http.posts[0]
    assert http.posts[0]["params"]["goal_fingerprint"] == contract.fingerprint()
    assert _run(home, http)[0] == 0
    assert len(http.posts) == 1


def test_stale_fingerprint_after_amendment_is_blocked(tmp_path):
    old = _contract().confirm("person:founder", "2026-10-13T12:00:00Z")
    new = old.amend(end_result="a different result").confirm("person:founder", "2026-10-13T13:00:00Z")
    home = _setup(tmp_path, _goal_spec(old), [old, new])
    http = FakeHTTP()
    assert _run(home, http)[0] == 0
    _assert_blocked_without_effect(home, http, "REVALIDATION_REQUIRED")


def test_unconfirmed_contract_is_blocked(tmp_path):
    from courier_core.goal_contract import _envelope
    contract = _contract()
    home = _home(tmp_path, {"A": _goal_spec(contract)})
    (home / "goal_contracts.jsonl").write_text(_envelope(contract), encoding="utf-8")
    _seed(home, [_ready("A", "a-assign")])
    http = FakeHTTP()
    assert _run(home, http)[0] == 0
    _assert_blocked_without_effect(home, http, "HUMAN_CONFIRMATION_REQUIRED")


def test_widened_scope_or_missing_anchor_is_blocked(tmp_path):
    contract = _contract().confirm("person:founder", "2026-10-13T12:00:00Z")
    for index, (task, word) in enumerate([
        ({"scope": ["out", "secrets"]}, "forbidden_scope"),
        ({"acceptance_ids": ["invented"]}, "criteria_changed"),
        ({"evidence_class": ""}, "NOT_VERIFIABLE"),
    ]):
        home = _setup(tmp_path / str(index), _goal_spec(contract, **task), [contract])
        http = FakeHTTP()
        assert _run(home, http)[0] == 0
        _assert_blocked_without_effect(home, http, word)


def test_missing_contract_for_goal_is_blocked(tmp_path):
    other = _contract(goal_id="goal-other").confirm("person:founder", "2026-10-13T12:00:00Z")
    contract = _contract()
    home = _setup(tmp_path, _goal_spec(contract), [other])
    http = FakeHTTP()
    assert _run(home, http)[0] == 0
    _assert_blocked_without_effect(home, http, "missing")


def test_without_contract_file_behaviour_is_unchanged(tmp_path):
    fp = hashlib.sha256(b"x").hexdigest()
    home = _home(tmp_path, {"A": _spec(goal_id="goal-1", goal_fingerprint=fp)})
    _seed(home, [_ready("A", "a-assign")])
    http = FakeHTTP()
    assert _run(home, http)[0] == 0
    assert len(http.posts) == 1
