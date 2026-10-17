import pytest

from courier_orchestrator.demo import build
from courier_orchestrator.hub import Hubwriter, HubwriterRejected, contract_for
from courier_orchestrator.models import GoalStatus, Task, TaskStatus, Verification
from courier_orchestrator.router import CostGovernor, route
from courier_orchestrator.workers import MockPruefer, MockWorker, default_registry


def _task():
    return Task("T1", "G", "spec", ("docs/",), "x", ("a",), 0.5)


def test_demo_end_to_end_done_with_cost():
    orch = build(bad_website=True)
    card = orch.run()
    assert card["status"] == "DONE"
    assert card["verified_results"] == 3
    assert card["budget"]["spent"] == pytest.approx(0.03 + 0.08 * 2 + 0.03 + 0.01 * 4)
    assert card["VERIFIED_USEFUL_RESULTS_PER_REAL_EURO"] > 0
    assert ("REJECTED", "T2", "NOT_VERIFIED") in orch.events
    assert [d.task_id for d in orch.hub.deltas] == ["T1", "T2", "T3"]


def test_own_pass_rejected():
    t = _task(); c = contract_for(t, "Produkt")
    r = MockWorker(default_registry()[0]).run(c, 1)
    own = Verification("T1", 1, r.worker_id, "PASS")
    with pytest.raises(HubwriterRejected) as e:
        Hubwriter().accept(c, r, own)
    assert e.value.code == "SELF_PASS_NOT_ACCEPTANCE"


def test_result_received_is_not_verified():
    t = _task(); c = contract_for(t, "Produkt")
    r = MockWorker(default_registry()[0]).run(c, 1)
    with pytest.raises(HubwriterRejected) as e:
        Hubwriter().accept(c, r, None)
    assert e.value.code == "RESULT_RECEIVED_NOT_VERIFIED"


def test_human_gate_stops():
    orch = build(actions_for_t3=("publication",))
    card = orch.run()
    assert card["status"] == "NEEDS_YOU"
    assert card["next_action"] == "HUMAN: T3"
    assert len(orch.hub.deltas) == 2


def test_unknown_external_effect_gated():
    orch = build(actions_for_t3=("send_newsletter",))
    orch.run()
    assert ("HUMAN_GATE", "T3", ("unknown_external_effect",)) in orch.events


def test_scope_escalation_rejected():
    t = _task(); c = contract_for(t, "Produkt")
    r = MockWorker(default_registry()[0], mode="escalate").run(c, 1)
    v = MockPruefer().verify(c, r)
    assert v.verdict == "FAIL" and "scope_exceeded" in v.reasons
    forged = Verification("T1", 1, "pruefer-mock", "PASS")
    with pytest.raises(HubwriterRejected) as e:
        Hubwriter().accept(c, r, forged)
    assert e.value.code == "SCOPE_ESCALATION"


def test_router_cheapest_sufficient_not_brand():
    from courier_orchestrator.models import Goal
    g = Goal("G", "P", "t", 1.0, "d")
    w = route(Task("T", "G", "spec", ("docs/",), "x", ("a",), 0.5), default_registry(), CostGovernor(g))
    assert w.worker_id == "tests-mock"   # cheapest with capability, not the "Chef"


def test_budget_exhausted_fails_closed():
    orch = build()
    orch.goal.budget_eur = 0.07
    card = orch.run()
    assert card["status"] == "FAILED"
