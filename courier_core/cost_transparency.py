"""Cost & Provider Transparency (No Hidden Spend).

Implements User Acceptance Requirement 03:
Derives customer-verifiable cost and provider transparency cards for Goals,
ensuring users can verify that zero incremental pay-as-you-go (PAYG) billing occurred
and that the financial budget firewall remained intact.
"""
from __future__ import annotations

from typing import Any, Mapping

COST_CLASS_FREE = "free"
COST_CLASS_LOW = "low"
COST_CLASS_MEDIUM = "medium"
COST_CLASS_HIGH = "high"

FIREWALL_INTACT = "INTACT"
FIREWALL_TRIGGERED = "PAYG_TRIGGERED"


def describe_billing_mode(cost_class: str, provider: str) -> str:
    """Format human-readable provider and billing mode description."""
    if isinstance(cost_class, bool) or (
        cost_class is not None and not isinstance(cost_class, str)
    ):
        cost_class = "unknown"
    elif cost_class == "":
        cost_class = "unknown"
    norm_class = (cost_class or COST_CLASS_FREE).lower()
    if isinstance(provider, bool) or (provider is not None and not isinstance(provider, str)):
        provider = "unknown"
    elif isinstance(provider, str) and not provider.strip():
        provider = "unknown"
    norm_provider = (provider or "local").title()

    if norm_class == COST_CLASS_FREE:
        return f"{norm_provider} Deterministic (FREE)"
    elif norm_class in (COST_CLASS_LOW, COST_CLASS_MEDIUM):
        return f"{norm_provider} Subscription (INCLUDED)"
    elif norm_class == COST_CLASS_HIGH:
        return f"{norm_provider} Metered (PAYG)"
    return f"{norm_provider} ({norm_class.upper()})"


def derive_goal_cost_summary(
    goal: Mapping[str, Any] | None,
    state: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Derives complete cost and provider transparency card for a goal.
    
    Guarantees:
    - Never charges or conceals pay-as-you-go (PAYG) external invocations.
    - Accurately reports budget firewall integrity.
    - Categorizes local execution vs subscription flatrate vs PAYG.
    """
    if not goal:
        return {
            "payg_spend_triggered": False,
            "estimated_marginal_cost": "0.00 EUR (No Active Plan)",
            "budget_firewall_status": FIREWALL_INTACT,
            "total_steps": 0,
            "steps_free": 0,
            "steps_included": 0,
            "steps_payg": 0,
            "provider_usage_breakdown": [],
            "human_summary": "Zero financial expenditure (no goal specified).",
        }

    state_dict = state or {}
    tasks_map = state_dict.get("tasks", {})
    workers_map = state_dict.get("workers", {})

    plan_invalid = "workflow_plan" in goal and not isinstance(goal.get("workflow_plan"), list)
    workflow_plan = goal.get("workflow_plan", [])
    if not isinstance(workflow_plan, list):
        workflow_plan = []

    breakdown: list[dict[str, Any]] = []
    steps_free = 0
    steps_included = 0
    steps_payg = 0
    payg_triggered = False

    for idx, step in enumerate(workflow_plan, start=1):
        if not isinstance(step, dict):
            steps_payg += 1
            payg_triggered = True
            continue
        task_id = step.get("task_id", f"step-{idx}")
        instruction = step.get("instruction", "Task step")
        task = tasks_map.get(task_id, {})

        worker_id = task.get("worker_id")
        if worker_id is None:
            worker_id = step.get("worker_id")
        if worker_id is None:
            worker = {}
        elif (
            isinstance(worker_id, bool)
            or not isinstance(worker_id, str)
            or not worker_id.strip()
            or worker_id not in workers_map
        ):
            worker = {"provider": "unknown"}
        else:
            worker = workers_map[worker_id]

        # Default unassigned / local steps to free
        provider = worker.get("provider")
        loaded = isinstance(worker_id, str) and worker_id in workers_map
        if provider is None and not loaded:
            target = step.get("target_agent")
            if target is None:
                provider = "local"
            elif isinstance(target, bool) or not isinstance(target, str) or not target.strip():
                provider = "unknown"
            else:
                provider = target
        elif (
            provider is None
            or isinstance(provider, bool)
            or not isinstance(provider, str)
            or not provider.strip()
        ):
            provider = "unknown"
        cost_class = worker.get("cost_class")
        if cost_class is None:
            cost_class = step.get("cost_class")
        if provider == "unknown":
            cost_class = "unknown"
        elif isinstance(cost_class, bool) or (
            cost_class is not None and not isinstance(cost_class, str)
        ):
            cost_class = "unknown"
        elif cost_class == "":
            cost_class = "unknown"
        elif not cost_class:
            if provider in ("local", "linux", "mac", "windows", "verifier"):
                cost_class = COST_CLASS_FREE
            else:
                cost_class = "unknown"  # UNKNOWN_COST: never assume included/free

        norm_cost = str(cost_class).lower()
        if norm_cost == COST_CLASS_FREE:
            steps_free += 1
        elif norm_cost in (COST_CLASS_LOW, COST_CLASS_MEDIUM):
            steps_included += 1
        else:
            steps_payg += 1
            payg_triggered = True

        billing_desc = describe_billing_mode(norm_cost, provider)
        breakdown.append({
            "step_index": idx,
            "task_id": task_id,
            "instruction": instruction,
            "provider": provider,
            "cost_class": norm_cost,
            "billing_mode": billing_desc,
            "worker_id": worker_id or "unassigned",
        })

    total_steps = len(workflow_plan)
    if plan_invalid:
        steps_payg += 1
        payg_triggered = True
        total_steps = 1
    if payg_triggered:
        marginal_cost = "Metered PAYG (Check provider credit consumption)"
        firewall_status = FIREWALL_TRIGGERED
        human_summary = (
            f"Goal triggered {steps_payg} pay-as-you-go step(s). "
            f"Financial budget firewall recorded external provider billing."
        )
    else:
        marginal_cost = "0.00 EUR (100% Flatrate / Local / Subscription)"
        firewall_status = FIREWALL_INTACT
        human_summary = (
            f"100% Zero-Spend Guaranteed: All {total_steps} step(s) executed on "
            f"local CPU ({steps_free}) or included developer subscriptions ({steps_included})."
        )

    return {
        "payg_spend_triggered": payg_triggered,
        "estimated_marginal_cost": marginal_cost,
        "budget_firewall_status": firewall_status,
        "total_steps": total_steps,
        "steps_free": steps_free,
        "steps_included": steps_included,
        "steps_payg": steps_payg,
        "provider_usage_breakdown": breakdown,
        "human_summary": human_summary,
    }
