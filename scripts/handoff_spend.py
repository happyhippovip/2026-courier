"""One spend decision for a handoff.

CostGate is the only policy. A missing estimate stays missing and is never
replaced with 0. This module does not post a task and does not sign anything.
"""

from __future__ import annotations


def marked_unknown_cost(body) -> bool:
    """True when the body says the cost is unknown, even if a number is also present."""
    if not isinstance(body, dict):
        return True
    marked = body.get("unknown_cost") is True or body.get("cost_class") == "unknown"
    params = body.get("params")
    if isinstance(params, dict):
        marked = marked or params.get("unknown_cost") is True or params.get("cost_class") == "unknown"
    return marked


def handoff_spend_block(body) -> str | None:
    """Return the CostGate reason, or None when this handoff may be posted.

    Explicit 0 EUR passes only when CostGate allows the active tier.
    A missing estimate stays missing. It is not replaced with 0.
    """
    from scripts.resource_policy import CostGate

    if not isinstance(body, dict) or marked_unknown_cost(body):
        return "UNKNOWN_COST"
    decision = CostGate.evaluate_spend_request(
        "google_antigravity_plus",
        estimated_cost_eur=body.get("estimated_cost_eur"),
        requested_action="HANDOFF",
    )
    if decision.get("allowed") is True:
        return None
    return str(decision.get("reason") or "UNKNOWN_COST")


def spend_body_from_parked(entry) -> dict:
    """Spend view of a parked wake. Cost fields are not task fields and are not posted.

    The view reads the task dict and the same three keys on the entry itself.
    A missing estimate is left missing. An entry mark or a blocking entry
    estimate is not hidden behind an explicit 0 on the task.
    """
    if not isinstance(entry, dict):
        return {}
    task = entry.get("task") if isinstance(entry.get("task"), dict) else {}
    body: dict = {}
    for key in ("estimated_cost_eur", "unknown_cost", "cost_class"):
        if key in task:
            body[key] = task[key]
    params = task.get("params")
    if isinstance(params, dict):
        body["params"] = params
    if entry.get("unknown_cost") is True:
        body["unknown_cost"] = True
    if entry.get("cost_class") == "unknown":
        body["cost_class"] = "unknown"
    if "estimated_cost_eur" not in entry:
        return body
    entry_cost = entry.get("estimated_cost_eur")
    if "estimated_cost_eur" not in body:
        body["estimated_cost_eur"] = entry_cost
        return body
    task_cost = body.get("estimated_cost_eur")
    # Show CostGate the estimate it would block. Do not keep a task zero
    # when the entry names a different, blocking amount.
    task_allowed = handoff_spend_block({"estimated_cost_eur": task_cost}) is None
    entry_blocked = handoff_spend_block({"estimated_cost_eur": entry_cost}) is not None
    if task_allowed and entry_blocked:
        body["estimated_cost_eur"] = entry_cost
    return body
