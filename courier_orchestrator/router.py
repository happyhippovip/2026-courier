"""Router + Cost Governor. Routes by capability, cost, availability, latency,
scope ownership, risk and verification quality -- never by brand name."""
from __future__ import annotations

from .models import Goal, Task
from .workers import WorkerProfile


class NoWorker(Exception):
    pass


class CostGovernor:
    """Cheapest sufficient capability first; tracks real spend."""

    def __init__(self, goal: Goal):
        self.goal = goal
        self.verified_useful = 0

    @property
    def remaining(self) -> float:
        return round(self.goal.budget_eur - self.goal.spent_eur, 6)

    def can_afford(self, cost: float, task: Task) -> bool:
        return cost <= task.cost_limit_eur and cost <= self.remaining

    def charge(self, cost: float) -> None:
        self.goal.spent_eur = round(self.goal.spent_eur + cost, 6)

    def metric(self) -> float:
        """VERIFIED_USEFUL_RESULTS_PER_REAL_EURO"""
        return round(self.verified_useful / self.goal.spent_eur, 3) if self.goal.spent_eur else 0.0


def score(w: WorkerProfile, task: Task) -> tuple:
    owns = any(s.startswith(o) for s in task.scope for o in w.owns_scope)
    # lower sorts first: cost dominates (cheapest sufficient), then quality/risk/ownership/latency
    return (round(w.cost_per_task_eur, 4), -round(w.verification_quality, 3), w.risk, not owns, w.latency_s, w.worker_id)


def route(task: Task, registry: list[WorkerProfile], governor: CostGovernor, exclude=()) -> WorkerProfile:
    candidates = [w for w in registry if w.available and task.capability in w.capabilities
                  and w.worker_id not in exclude and governor.can_afford(w.cost_per_task_eur, task)]
    if not candidates:
        raise NoWorker(task.task_id)
    return sorted(candidates, key=lambda w: score(w, task))[0]
