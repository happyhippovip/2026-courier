"""Einstein Layer slice: Mission Compiler, utility score, TRUST(worker, task_class),
result binding with minimal context, independent reviewer, conflict handling.

Mock workers only. Nothing here calls a live provider or claims a live result.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from .hub import Hubwriter, HubwriterRejected, contract_for
from .models import Goal, GoalStatus, Result, Task, TaskStatus, Verification


def utility(value: float, cost: float, risk: float = 0.0, uncertainty: float = 0.0, delay: float = 0.0) -> float:
    """EXPECTED_UTILITY = EXPECTED_VALUE - COST - RISK_PENALTY - UNCERTAINTY_PENALTY - DELAY_PENALTY"""
    return round(value - cost - risk - uncertainty - delay, 4)


class TrustGraph:
    """TRUST(worker, task_class), fed only by independent verification outcomes."""

    def __init__(self):
        self._v: dict[tuple, list[int]] = {}

    def record(self, worker: str, task_class: str, verification: Verification, result_worker: str) -> None:
        if verification.verifier_id == result_worker:
            return                               # self-certification never moves trust
        p, n = self._v.setdefault((worker, task_class), [0, 0])
        self._v[(worker, task_class)] = [p + (verification.verdict == "PASS"), n + 1]

    def trust(self, worker: str, task_class: str) -> float:
        p, n = self._v.get((worker, task_class), [0, 0])
        return round((p + 1) / (n + 2), 3)


@dataclass
class CompiledTask:
    task: Task
    why_this_task_exists: str
    goal_delta: str
    evidence: str
    why_now: str
    why_this_worker: str
    expected_value: float
    context_keys: tuple = ()       # minimal context: only bound results it needs


@dataclass
class Mission:
    goal: Goal
    success_conditions: tuple
    constraints: tuple
    required_evidence: tuple
    tasks: list = field(default_factory=list)
    verification_plan: str = "independent reviewer per task; hubwriter writes only after PASS"


def compile_mission(goal: Goal) -> Mission:
    """Mission -> Success Conditions -> Constraints -> Evidence -> Tasks -> Verification Plan."""
    m = Mission(goal,
                success_conditions=("clear_value_prop", "landing_section_uses_message"),
                constraints=("no_publication_without_human", "no_edit:server/app.py", f"budget<={goal.budget_eur}EUR"),
                required_evidence=("message_doc", "html_diff"))
    m.tasks = [
        CompiledTask(Task("PRODUCT-1", goal.goal_id, "message", ("docs/product/",), "Produktbotschaft",
                          ("one_sentence", "three_benefits"), 0.2),
                     "Website braucht eine geprüfte Kernbotschaft", "clear_value_prop", "message_doc",
                     "blockiert die Website", "Product: billigste Fähigkeit 'message'", 3.0),
        CompiledTask(Task("WEBSITE-1", goal.goal_id, "web", ("website/",), "Landing-Hero-Entwurf",
                          ("uses_message", "no_new_claims"), 0.2, depends_on=("PRODUCT-1",)),
                     "Botschaft sichtbar machen", "landing_section_uses_message", "html_diff",
                     "PRODUCT-1 ist akzeptiert", "Website: besitzt scope website/", 2.5,
                     context_keys=("PRODUCT-1",)),
    ]
    return m


class MockProduct:
    worker_id, role, cost = "product-mock", "Product", 0.04

    def run(self, contract, ctx, attempt):
        out = {"one_sentence": "[MOCK] Du sagst das Ziel, Courier liefert geprüfte Ergebnisse.",
               "three_benefits": ["kein Copy/Paste", "nur Geprüftes zählt", "du wirst nur bei Gates gefragt"]}
        return Result(contract.task_id, contract.goal_id, attempt, self.worker_id, out,
                      contract.allowed_scope, self.cost, ("mock://product/1",), "PASS")


class MockWebsite:
    worker_id, role, cost = "website-mock", "Website", 0.06

    def run(self, contract, ctx, attempt):
        msg = ctx["PRODUCT-1"]["one_sentence"]
        # attempt 1 invents a claim that the bound message does not contain -> conflict
        extra = " 10x schneller als jedes Team." if attempt == 1 else ""
        out = {"hero_html": f"<h1>{msg}{extra}</h1>", "bound_from": "PRODUCT-1"}
        return Result(contract.task_id, contract.goal_id, attempt, self.worker_id, out,
                      contract.allowed_scope, self.cost, (f"mock://website/{attempt}",), "PASS")


class MockReviewer:
    verifier_id, cost = "reviewer-mock", 0.01

    def review(self, ct: CompiledTask, result: Result, ctx: dict) -> Verification:
        reasons = []
        o = result.output
        if ct.task.task_id == "PRODUCT-1":
            if not o.get("one_sentence") or len(o.get("three_benefits", [])) != 3:
                reasons.append("criteria_missing")
        else:
            msg = ctx["PRODUCT-1"]["one_sentence"]
            if msg not in o.get("hero_html", ""):
                reasons.append("message_not_used")
            elif o["hero_html"] != f"<h1>{msg}</h1>":
                reasons.append("CONFLICT:new_claim_not_in_message")
        return Verification(result.task_id, result.attempt, self.verifier_id,
                            "FAIL" if reasons else "PASS", tuple(reasons), self.cost)


def run_experiment(max_attempts: int = 2) -> dict:
    t0 = time.monotonic()
    goal = Goal("G-LANDING-1", "P-COURIER", "Verbessere die Courier-Symphony-Landingpage und ihre Produktbotschaft",
                1.0, "2026-10-20")
    mission = compile_mission(goal)
    workers = {"message": MockProduct(), "web": MockWebsite()}
    reviewer, hub, trust = MockReviewer(), Hubwriter(), TrustGraph()
    bound: dict[str, dict] = {}            # RESULT_BINDING: accepted outputs keyed by task_id
    events, unverified_done = [], 0
    for ct in mission.tasks:
        t = ct.task
        if not ct.goal_delta:
            events.append(("SKIPPED_NO_GOAL_DELTA", t.task_id)); continue
        w = workers[t.capability]
        u = utility(ct.expected_value, w.cost, uncertainty=1 - trust.trust(w.worker_id, t.capability))
        if u <= 0:
            events.append(("SKIPPED_LOW_UTILITY", t.task_id, u)); continue
        ctx = {k: bound[k] for k in ct.context_keys}      # minimal context only
        contract = contract_for(t, w.role)
        while t.attempts < max_attempts and t.status != TaskStatus.ACCEPTED:
            t.attempts += 1
            r = w.run(contract, ctx, t.attempts)
            goal.spent_eur = round(goal.spent_eur + r.cost_eur, 4)
            events.append(("RESULT_RECEIVED", t.task_id, t.attempts))
            v = reviewer.review(ct, r, ctx)
            goal.spent_eur = round(goal.spent_eur + v.cost_eur, 4)
            trust.record(w.worker_id, t.capability, v, r.worker_id)
            try:
                hub.accept(contract, r, v)
            except HubwriterRejected as e:
                events.append(("REJECTED", t.task_id, e.code, v.reasons)); continue
            bound[t.task_id] = r.output
            t.status = TaskStatus.ACCEPTED
            events.append(("ACCEPTED", t.task_id, t.attempts))
        if t.status != TaskStatus.ACCEPTED:
            goal.status = GoalStatus.NEEDS_YOU
            events.append(("NEEDS_YOU", t.task_id)); break
    if goal.status == GoalStatus.WORKING:
        goal.status = GoalStatus.DONE
    writers = {d.writer for d in hub.deltas}
    return {
        "GOAL_STATUS": goal.status.value,
        "MANUAL_COPY_PASTE": 0,
        "RESULT_BINDING": "YES" if "PRODUCT-1" in bound and bound.get("WEBSITE-1", {}).get("bound_from") == "PRODUCT-1" else "NO",
        "CANONICAL_WRITERS": len(writers),
        "UNVERIFIED_CLAIMS_AS_DONE": unverified_done,
        "TOTAL_COST": f"{goal.spent_eur:.2f} EUR (mock)",
        "TOTAL_TIME": f"{time.monotonic() - t0:.3f} s (mock)",
        "VERIFIED_OUTPUTS": len(hub.deltas),
        "HUMAN_INTERRUPTS": sum(1 for e in events if e[0] == "NEEDS_YOU"),
        "TRUST": {f"{w.worker_id}/{c}": trust.trust(w.worker_id, c) for c, w in workers.items()},
        "events": events,
    }


def main() -> int:
    import json
    out = run_experiment()
    for k, v in out.items():
        print(f"{k}={json.dumps(v, default=str) if not isinstance(v, (str, int)) else v}")
    return 0 if out["GOAL_STATUS"] == "DONE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
