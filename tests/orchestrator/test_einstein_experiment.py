from courier_orchestrator.mission import TrustGraph, compile_mission, run_experiment, utility
from courier_orchestrator.models import Goal, Verification


def test_experiment_end_to_end():
    o = run_experiment()
    assert o["GOAL_STATUS"] == "DONE"
    assert o["MANUAL_COPY_PASTE"] == 0 and o["RESULT_BINDING"] == "YES"
    assert o["CANONICAL_WRITERS"] == 1 and o["UNVERIFIED_CLAIMS_AS_DONE"] == 0
    assert o["VERIFIED_OUTPUTS"] == 2 and o["HUMAN_INTERRUPTS"] == 0
    assert o["TOTAL_COST"].startswith("0.19")
    assert any(e[0] == "REJECTED" and "CONFLICT:new_claim_not_in_message" in e[3] for e in o["events"])


def test_conflict_unresolved_needs_human():
    o = run_experiment(max_attempts=1)
    assert o["GOAL_STATUS"] == "NEEDS_YOU" and o["HUMAN_INTERRUPTS"] == 1 and o["VERIFIED_OUTPUTS"] == 1


def test_every_task_has_goal_delta_and_why():
    m = compile_mission(Goal("G", "P", "t", 1.0, "d"))
    for ct in m.tasks:
        assert ct.goal_delta in m.success_conditions
        assert all([ct.why_this_task_exists, ct.evidence, ct.why_now, ct.why_this_worker])


def test_trust_ignores_self_certification():
    tg = TrustGraph()
    tg.record("w", "web", Verification("T", 1, "w", "PASS"), "w")
    assert tg.trust("w", "web") == 0.5
    tg.record("w", "web", Verification("T", 1, "rev", "PASS"), "w")
    assert tg.trust("w", "web") > 0.5


def test_utility_formula():
    assert utility(3, 0.5, 0.5, 0.25, 0.25) == 1.5
