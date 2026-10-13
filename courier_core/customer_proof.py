"""Customer reading of a goal contract.

Success is shown only when validate_task already accepted the task.
Missing rights are sentences for those reason codes. They do not decide
again, and they do not include who confirmed the terms.

First-pilot bounds are a pinned reading of the existing pilot spec and
product-plan sections 14–16. They are not a launch and not a payment link.
"""

from __future__ import annotations

from dataclasses import dataclass

from courier_core.goal_contract import GoalContract, Verdict

_PLAIN = {
    "unconfirmed": "Missing right: a person has not confirmed these terms.",
    "stale_fingerprint": "Missing right: the terms changed and need confirmation again.",
    "criteria_changed": "Missing right: the acceptance criteria are not the confirmed ones.",
    "missing_acceptance_anchor": "Missing right: there is no acceptance anchor to show.",
    "missing_evidence_class": "Missing right: the evidence class is missing.",
    "evidence_class_mismatch": "Missing right: the evidence class does not match the acceptance anchor.",
    "goal_id_mismatch": "Missing right: the task names a different goal.",
    "missing_goal_id": "Missing right: the task names no goal.",
    "missing_fingerprint": "Missing right: the task names no terms fingerprint.",
    "unknown_field": "Missing right: the task has a field that is not part of the contract.",
    "task_spec_invalid": "Missing right: the task is not a record.",
    "scope_invalid": "Missing right: the task scope is not a list of allowed items.",
}


@dataclass(frozen=True)
class CustomerCard:
    goal_id: str
    fingerprint: str
    success: bool
    evidence: tuple[str, ...]
    missing_rights: tuple[str, ...]


@dataclass(frozen=True)
class PilotBounds:
    inside: tuple[str, ...]
    outside: tuple[str, ...]


_FIRST_PILOT = PilotBounds(
    inside=(
        "human-confirmed goal contract",
        "accepted task shown with its acceptance check",
        "accompanied manual setup",
    ),
    outside=(
        "payments",
        "git push",
        "deploy",
        "marketplace",
        "secrets",
        "published payment link",
    ),
)


def customer_card(contract: GoalContract, task_spec: object) -> CustomerCard:
    """Fail closed: an unaccepted task has no customer evidence."""
    validation = contract.validate_task(task_spec)
    if validation.verdict is not Verdict.ACCEPTED:
        return CustomerCard(
            contract.goal_id,
            contract.fingerprint(),
            False,
            (),
            _missing(contract, task_spec, validation.reasons),
        )
    evidence = _evidence(contract, task_spec)
    if not evidence:
        return CustomerCard(
            contract.goal_id,
            contract.fingerprint(),
            False,
            (),
            ("Missing right: there is nothing accepted to show.",),
        )
    return CustomerCard(contract.goal_id, contract.fingerprint(), True, evidence, ())


def first_pilot_bounds() -> PilotBounds:
    """Same bounds on every call. Acceptance of a task does not move them."""
    return _FIRST_PILOT


def _evidence(contract: GoalContract, task_spec: object) -> tuple[str, ...]:
    if not isinstance(task_spec, dict):
        return ()
    anchors = task_spec.get("acceptance_ids")
    if not isinstance(anchors, (list, tuple)):
        return ()
    wanted = {item.strip() for item in anchors if isinstance(item, str)}
    return tuple(
        f"Shown: {item.id} — {item.check}."
        for item in contract.acceptance_criteria
        if item.id in wanted
    )


def _missing(contract: GoalContract, task_spec: object, reasons: tuple[str, ...]) -> tuple[str, ...]:
    scope = _scope_items(task_spec)
    lines = []
    for reason in reasons:
        if reason == "forbidden_scope":
            items = ", ".join(sorted(scope & set(contract.forbidden_scope)))
            lines.append(f"Missing right: scope includes forbidden {items}.")
        elif reason == "scope_widened":
            items = ", ".join(sorted(scope - set(contract.allowed_scope)))
            lines.append(f"Missing right: scope adds {items}, which is outside the allowed scope.")
        else:
            lines.append(_PLAIN.get(reason, f"Missing right: {reason}."))
    return tuple(lines)


def _scope_items(task_spec: object) -> set[str]:
    if not isinstance(task_spec, dict):
        return set()
    value = task_spec.get("scope")
    if not isinstance(value, (list, tuple)):
        return set()
    items = set()
    for item in value:
        if isinstance(item, str) and item.strip() and "\n" not in item and "\r" not in item:
            items.add(item.strip())
    return items
