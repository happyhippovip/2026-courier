"""Customer proof: success only when accepted, missing rights named, pilot bounds pinned."""

from courier_core.customer_proof import customer_card, first_pilot_bounds
from courier_core.goal_contract import (
    AcceptanceCriterion,
    Gates,
    GoalContract,
    GoalContractStore,
    Verdict,
)


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


def _confirmed():
    return _contract().confirm("person:ada", "2026-10-08T00:00:00Z")


def test_unaccepted_task_is_not_shown_as_customer_success():
    contract = _contract()
    card = customer_card(contract, _task(contract, scope=["docs", "production"]))
    assert card.success is False
    assert card.evidence == ()
    assert card.missing_rights == ("Missing right: a person has not confirmed these terms.",)
    shown = " ".join(card.evidence + card.missing_rights)
    assert "Shown:" not in shown
    assert "person:ada" not in shown
    assert "Confirmed by" not in shown
    assert card.goal_id == "goal-1"
    assert card.fingerprint == contract.fingerprint()
    assert contract.validate_task(_task(contract)).verdict == Verdict.HUMAN_CONFIRMATION_REQUIRED


def test_accepted_task_shows_only_the_anchored_check():
    contract = _confirmed()
    card = customer_card(contract, _task(contract))
    assert card.success is True
    assert card.evidence == ("Shown: docs-present — the document exists.",)
    assert card.missing_rights == ()
    assert "tests-pass" not in " ".join(card.evidence)
    assert "person:ada" not in " ".join(card.evidence)
    both = customer_card(
        contract,
        _task(contract, scope=["tests", "docs"], acceptance_ids=["tests-pass", "docs-present"]),
    )
    assert both.evidence == (
        "Shown: docs-present — the document exists.",
        "Shown: tests-pass — the targeted tests pass.",
    )


def test_payments_names_forbidden_and_widened_and_hides_the_actor():
    contract = _confirmed()
    card = customer_card(contract, _task(contract, scope=["payments"]))
    assert card.success is False
    assert card.evidence == ()
    assert card.missing_rights == (
        "Missing right: scope includes forbidden payments.",
        "Missing right: scope adds payments, which is outside the allowed scope.",
    )
    assert "person:ada" not in repr(card)
    widened = customer_card(contract, _task(contract, scope=["docs", "production"]))
    assert widened.missing_rights == (
        "Missing right: scope adds production, which is outside the allowed scope.",
    )
    stale = customer_card(contract.amend(constraints=["no network", "no spend"]), _task(contract))
    assert stale.success is False
    assert stale.missing_rights == ("Missing right: the terms changed and need confirmation again.",)
    assert contract.validate_task(_task(contract, scope=["payments"])).reasons == (
        "forbidden_scope",
        "scope_widened",
    )


def test_card_survives_reload_and_a_second_call(tmp_path):
    contract = _confirmed()
    task = _task(contract)
    store = GoalContractStore(tmp_path / "goals.jsonl")
    store.append(contract)
    loaded = store.read()[0]
    assert customer_card(loaded, task) == customer_card(contract, task)
    assert customer_card(loaded, task) == customer_card(loaded, task)
    assert loaded.validate_task(task).verdict == Verdict.ACCEPTED


def test_first_pilot_bounds_keep_payments_push_and_deploy_outside():
    bounds = first_pilot_bounds()
    assert bounds.inside == (
        "human-confirmed goal contract",
        "accepted task shown with its acceptance check",
        "accompanied manual setup",
    )
    assert bounds.outside == (
        "payments",
        "git push",
        "deploy",
        "marketplace",
        "secrets",
        "published payment link",
    )
    assert set(bounds.inside).isdisjoint(bounds.outside)
    text = " ".join(bounds.inside + bounds.outside)
    assert "http" not in text
    assert "://" not in text
    card = customer_card(_confirmed(), _task(_confirmed()))
    assert card.success is True
    assert "payments" in first_pilot_bounds().outside
    assert first_pilot_bounds() == bounds
