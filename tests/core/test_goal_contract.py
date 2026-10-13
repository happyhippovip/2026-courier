"""Goal Contract fingerprint, human confirmation, and task-scope validation."""

import json
from pathlib import Path

import pytest

from courier_core.goal_contract import (
    MAX_FILE_BYTES,
    AcceptanceCriterion,
    Gates,
    GoalContract,
    GoalContractError,
    GoalContractStore,
    Verdict,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "courier_core" / "schemas" / "goal_contract.schema.json"


def _criteria(*pairs):
    return [AcceptanceCriterion(item_id, check, "deterministic") for item_id, check in pairs]


def _contract(**overrides):
    values = dict(
        goal_id="goal-1",
        end_result="the stated result is present",
        allowed_scope=["docs", "tests"],
        forbidden_scope=["secrets", "payments"],
        constraints=["no network"],
        acceptance_criteria=_criteria(("docs-present", "the document exists"), ("tests-pass", "the targeted tests pass")),
        side_effect_limits=["no commits"],
        gates=Gates(human=True, money=True, safety=True),
    )
    values.update(overrides)
    return GoalContract(**values)


def _task(contract, **overrides):
    spec = {
        "goal_id": contract.goal_id,
        "goal_fingerprint": contract.fingerprint(),
        "scope": ["docs"],
        "acceptance_ids": ["docs-present"],
        "evidence_class": "deterministic",
    }
    spec.update(overrides)
    return spec


def test_fingerprint_stable_under_reorder_and_changes_when_terms_change():
    left = _contract(
        allowed_scope=["tests", "docs", "docs"],
        forbidden_scope=["payments", "secrets"],
        constraints=["no network"],
        acceptance_criteria=[
            AcceptanceCriterion("tests-pass", "the targeted tests pass", "deterministic"),
            AcceptanceCriterion("docs-present", "the document exists", "deterministic"),
        ],
    )
    right = _contract()
    assert left.fingerprint() == right.fingerprint()
    assert len(left.fingerprint()) == 64

    confirmed = left.confirm("person:ada", "2026-10-08T00:00:00Z")
    assert confirmed.fingerprint() == left.fingerprint()
    assert confirmed.human_confirmed
    assert not left.human_confirmed

    changed = [
        _contract(end_result="a different result"),
        _contract(allowed_scope=["docs"]),
        _contract(forbidden_scope=["secrets", "payments", "production"]),
        _contract(constraints=["no network", "no spend"]),
        _contract(acceptance_criteria=_criteria(("docs-present", "the document is signed"))),
        _contract(acceptance_criteria=[AcceptanceCriterion("docs-present", "the document exists", "independent")]),
        _contract(side_effect_limits=["no commits", "no deploy"]),
        _contract(gates=Gates(human=True, money=False, safety=True)),
        _contract(goal_id="goal-2"),
    ]
    assert len({item.fingerprint() for item in changed}) == len(changed)
    assert left.fingerprint() not in {item.fingerprint() for item in changed}


def test_unconfirmed_contract_requires_human_confirmation():
    contract = _contract()
    tasks = [
        _task(contract),
        _task(contract, scope=["docs", "tests", "production"]),
        _task(contract, acceptance_ids=[]),
        _task(contract, evidence_class=""),
        {"goal_id": contract.goal_id},
        "not-a-task",
    ]
    for spec in tasks:
        result = contract.validate_task(spec)
        assert result.verdict == Verdict.HUMAN_CONFIRMATION_REQUIRED
        assert result.reasons == ("unconfirmed",)
        assert result.verdict != Verdict.ACCEPTED

    with pytest.raises(GoalContractError, match="human"):
        contract.confirm("person:ada", "2026-10-08T00:00:00Z", actor_kind="agent")
    assert contract.confirmations == ()


def test_narrowing_accepted_widening_forbidden_or_criteria_change_requires_human():
    contract = _contract().confirm("person:ada", "2026-10-08T00:00:00Z")
    narrowed = contract.validate_task(_task(contract, scope=["docs"]))
    assert narrowed.verdict == Verdict.ACCEPTED
    assert narrowed.reasons == ()

    both = contract.validate_task(_task(contract, scope=["tests", "docs"], acceptance_ids=["tests-pass", "docs-present"]))
    assert both.verdict == Verdict.ACCEPTED

    widened = contract.validate_task(_task(contract, scope=["docs", "production"]))
    assert widened.verdict == Verdict.HUMAN_CONFIRMATION_REQUIRED
    assert "scope_widened" in widened.reasons

    forbidden = contract.validate_task(_task(contract, scope=["payments"]))
    assert forbidden.verdict == Verdict.HUMAN_CONFIRMATION_REQUIRED
    assert "forbidden_scope" in forbidden.reasons

    criteria = contract.validate_task(_task(contract, acceptance_ids=["docs-present", "uncontracted"]))
    assert criteria.verdict == Verdict.HUMAN_CONFIRMATION_REQUIRED
    assert criteria.reasons == ("criteria_changed",)
    assert criteria.verdict != Verdict.ACCEPTED


def test_missing_acceptance_anchor_or_evidence_class_is_not_verifiable():
    contract = _contract().confirm("person:ada", "2026-10-08T00:00:00Z")
    cases = [
        _task(contract, acceptance_ids=[]),
        _task(contract, acceptance_ids=None),
        {key: value for key, value in _task(contract).items() if key != "acceptance_ids"},
        _task(contract, evidence_class=""),
        _task(contract, evidence_class=None),
        {key: value for key, value in _task(contract).items() if key != "evidence_class"},
        _task(contract, evidence_class="self_reported"),
    ]
    for spec in cases:
        result = contract.validate_task(spec)
        assert result.verdict == Verdict.NOT_VERIFIABLE
        assert result.verdict != Verdict.ACCEPTED
        assert result.reasons


def test_stale_fingerprint_after_amendment_requires_revalidation():
    original = _contract().confirm("person:ada", "2026-10-08T00:00:00Z")
    bound = _task(original)
    assert original.validate_task(bound).verdict == Verdict.ACCEPTED

    amended = original.amend(allowed_scope=["docs", "tests", "notes"])
    assert amended.goal_id == original.goal_id
    assert amended.fingerprint() != original.fingerprint()
    assert amended.confirmations == ()

    stale = amended.validate_task(bound)
    assert stale.verdict == Verdict.REVALIDATION_REQUIRED
    assert stale.reasons == ("stale_fingerprint",)
    assert stale.verdict != Verdict.ACCEPTED

    rebound = _task(amended)
    assert amended.validate_task(rebound).verdict == Verdict.HUMAN_CONFIRMATION_REQUIRED
    again = amended.confirm("person:ada", "2026-10-08T01:00:00Z")
    assert again.fingerprint() == amended.fingerprint()
    assert again.validate_task(rebound).verdict == Verdict.ACCEPTED
    assert again.validate_task(bound).verdict == Verdict.REVALIDATION_REQUIRED


def test_store_round_trip_and_fail_closed(tmp_path):
    path = tmp_path / "goals.jsonl"
    store = GoalContractStore(path)
    first = _contract().confirm("person:ada", "2026-10-08T00:00:00Z")
    second = first.amend(constraints=["no network", "no spend"]).confirm("person:ada", "2026-10-08T02:00:00Z")
    store.append(first)
    store.append(second)
    loaded = store.read()
    assert len(loaded) == 2
    assert loaded[0].fingerprint() == first.fingerprint()
    assert loaded[0].to_record() == first.to_record()
    assert loaded[1].fingerprint() == second.fingerprint()
    assert [item.actor_ref for item in loaded[1].confirmations] == ["person:ada"]

    original = path.read_text(encoding="utf-8")
    tampered = original.replace("the stated result is present", "a substituted result", 1)
    assert tampered != original
    path.write_text(tampered, encoding="utf-8")
    with pytest.raises(GoalContractError, match="tampered"):
        store.read()

    record = first.to_record()
    record["note"] = "smuggled"
    payload = {"contract": record, "sha256": "0" * 64}
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(GoalContractError, match="unknown field"):
        store.read()

    path.write_bytes(b"x" * (MAX_FILE_BYTES + 1))
    with pytest.raises(GoalContractError, match="1 MiB"):
        store.read()

    fresh = tmp_path / "fresh.jsonl"
    fresh.write_bytes(b"y" * MAX_FILE_BYTES)
    with pytest.raises(GoalContractError, match="1 MiB"):
        GoalContractStore(fresh).append(first)
    assert fresh.read_bytes() == b"y" * MAX_FILE_BYTES


def test_schema_rejects_unknown_fields():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "goal_id",
        "end_result",
        "allowed_scope",
        "forbidden_scope",
        "constraints",
        "acceptance_criteria",
        "side_effect_limits",
        "gates",
        "confirmations",
    }
    assert schema["properties"]["confirmations"]["items"]["properties"]["actor_kind"]["const"] == "human"
    assert schema["properties"]["gates"]["additionalProperties"] is False
    assert schema["properties"]["acceptance_criteria"]["items"]["additionalProperties"] is False
