"""Confirmed dispatch contract for tests. Production code never calls this."""

from pathlib import Path

from courier_core.goal_contract import (
    GOAL_CONTRACTS_FILE, GoalContractStore, confirm_draft, draft_goal_contract,
)

DISPATCH_GOAL = {
    "goal_id": "goal-dispatch",
    "end_result": "the probe artifact matches its sha256",
    "allowed_scope": ["probe", "out.txt", "stated-result", "docs", "synthetic"],
    "forbidden_scope": ["secrets"],
    "constraints": ["no network"],
    "acceptance_criteria": [
        {"id": "stated-result", "check": "the probe artifact matches its sha256", "evidence_class": "deterministic"},
    ],
    "side_effect_limits": ["no commits"],
    "gates": {"human": True, "money": False, "safety": True},
}
ACTOR = "person:ada"
CONFIRMED_AT = "2026-10-15T12:00:00Z"


def confirmed_contract():
    draft = draft_goal_contract(DISPATCH_GOAL)
    if draft.contract is None:
        raise RuntimeError("dispatch goal did not draft")
    return confirm_draft(draft.contract, ACTOR, CONFIRMED_AT, authenticated=True)


def task_view(contract=None, scope=None):
    contract = confirmed_contract() if contract is None else contract
    return {
        "goal_id": contract.goal_id,
        "goal_fingerprint": contract.fingerprint(),
        "scope": ["probe"] if scope is None else scope,
        "acceptance_ids": ["stated-result"],
        "evidence_class": "deterministic",
    }


def install_dispatch_contract(home):
    """Append the confirmed contract once. A second call leaves the file as it is."""
    path = Path(home) / GOAL_CONTRACTS_FILE
    if path.exists():
        return confirmed_contract()
    contract = confirmed_contract()
    GoalContractStore(path).append(contract)
    return contract
