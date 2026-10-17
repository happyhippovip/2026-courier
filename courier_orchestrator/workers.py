"""Worker registry and mock adapters. Mock = deterministic, no live claims."""
from __future__ import annotations

from dataclasses import dataclass

from .models import Result, Verification, WorkerContract

COURIER_ROLES = ("Courier Grok", "Umsatz", "Produkt", "Integration", "Website", "Pruefer",
                 "Katalog", "Tests", "Datenrettung", "Wand-Aufsicht", "Vogel")


@dataclass
class WorkerProfile:
    worker_id: str
    role: str
    capabilities: frozenset
    cost_per_task_eur: float
    latency_s: float
    available: bool = True
    owns_scope: tuple = ()
    risk: float = 0.1                  # 0 (safe) .. 1
    verified: int = 0
    rejected: int = 0
    mock: bool = True

    @property
    def verification_quality(self) -> float:
        n = self.verified + self.rejected
        return (self.verified + 1) / (n + 2)   # Laplace prior


class MockWorker:
    """Executes a contract deterministically. `mode` lets tests misbehave."""

    def __init__(self, profile: WorkerProfile, mode: str = "ok"):
        self.profile = profile
        self.mode = mode

    def run(self, contract: WorkerContract, attempt: int) -> Result:
        scope = tuple(contract.allowed_scope)
        if self.mode == "escalate":
            scope = scope + ("server/app.py",)
        output = {"summary": f"[MOCK] {self.profile.role}: {contract.expected_output}",
                  "criteria_met": list(contract.acceptance_criteria)}
        if self.mode == "bad" and attempt == 1:
            output["criteria_met"] = []
        return Result(task_id=contract.task_id, goal_id=contract.goal_id, attempt=attempt,
                      worker_id=self.profile.worker_id, output=output, requested_scope=scope,
                      cost_eur=self.profile.cost_per_task_eur,
                      evidence=(f"mock://{contract.task_id}/{attempt}",), self_verdict="PASS")


class MockPruefer:
    """Independent verifier: checks criteria coverage and scope."""

    def __init__(self, verifier_id: str = "pruefer-mock", cost_eur: float = 0.01):
        self.verifier_id = verifier_id
        self.cost_eur = cost_eur

    def verify(self, contract: WorkerContract, result: Result) -> Verification:
        reasons = []
        missing = set(contract.acceptance_criteria) - set(result.output.get("criteria_met", []))
        if missing:
            reasons.append("criteria_missing:" + ",".join(sorted(missing)))
        if not set(result.requested_scope) <= set(contract.allowed_scope):
            reasons.append("scope_exceeded")
        if not result.evidence:
            reasons.append("no_evidence")
        return Verification(result.task_id, result.attempt, self.verifier_id,
                            "FAIL" if reasons else "PASS", tuple(reasons), self.cost_eur)


def default_registry() -> list[WorkerProfile]:
    return [
        WorkerProfile("produkt-mock", "Produkt", frozenset({"spec", "copy"}), 0.05, 20, owns_scope=("docs/",)),
        WorkerProfile("website-mock", "Website", frozenset({"web", "copy"}), 0.08, 30, owns_scope=("website/",)),
        WorkerProfile("tests-mock", "Tests", frozenset({"tests", "spec"}), 0.03, 15, owns_scope=("tests/",)),
        WorkerProfile("courier-grok-mock", "Courier Grok", frozenset({"spec", "web", "tests", "copy"}), 0.40, 10),
    ]
