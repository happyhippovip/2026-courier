import pytest
from courier_core.state_machine import TaskState, TaskStatus
from courier_hub import model

def make_task(status, **kwargs):
    base = {
        "task_id": "task-test-1",
        "status": TaskStatus(status) if isinstance(status, str) and hasattr(TaskStatus, status) else status,
        "adapter": "synthetic",
        "params": {"title": "Test Operation"},
        "effect_class": "non_idempotent",
        "max_attempts": 3,
        "lease_ttl_s": 10,
        "timeout_s": 30,
        "attempt": 1,
    }
    base.update(kwargs)
    return TaskState(**base)

def test_pile_of_comprehensive_matrix():
    assert model.pile_of(make_task("BLOCKED")) == model.PILE_NEEDS_YOU
    for st in ["QUEUED", "CLAIMED", "RUNNING", "VERIFYING", "ACCEPTED", "RETRY_PENDING"]:
        assert model.pile_of(make_task(st)) == model.PILE_WORKING
    for st in ["COMPLETE", "FAILED", "CANCELLED"]:
        assert model.pile_of(make_task(st)) == model.PILE_DONE

    # Dict input compatibility
    assert model.pile_of({"status": "BLOCKED"}) == model.PILE_NEEDS_YOU
    assert model.pile_of({"status": "RUNNING"}) == model.PILE_WORKING
    assert model.pile_of({"status": "COMPLETE"}) == model.PILE_DONE

    with pytest.raises(ValueError, match="unknown task status"):
        model.pile_of({"status": "INVALID_STATUS_XYZ"})

def test_working_phase_mappings():
    # Stopping overrides any working status
    assert model.working_phase(make_task("RUNNING", cancel_requested=True))["phase"] == "stopping"
    assert model.working_phase(make_task("QUEUED", cancel_requested=True))["phase"] == "stopping"

    # Standard working phases
    assert model.working_phase(make_task("QUEUED"))["phase"] == "waiting"
    assert model.working_phase(make_task("CLAIMED"))["phase"] == "in_progress"
    assert model.working_phase(make_task("RUNNING"))["phase"] == "in_progress"
    assert model.working_phase(make_task("RETRY_PENDING"))["phase"] == "in_progress"
    assert model.working_phase(make_task("VERIFYING"))["phase"] == "checking"
    assert model.working_phase(make_task("ACCEPTED"))["phase"] == "checking"

def test_outcome_copy_actor_formatting_and_explanations():
    # Human confirmed actor sanitization: strip "desktop:" prefix
    task_human = make_task("COMPLETE", resolution="effect_confirmed", decided_by="desktop:dennis_lead")
    outcome_human = model.outcome_copy(task_human)
    assert outcome_human["outcome"] == model.OUTCOME_HUMAN_CONFIRMED
    assert outcome_human["label"] == "Confirmed by dennis_lead"
    assert outcome_human["mark"] == "signature"

    # Default actor when decided_by is missing
    task_no_actor = make_task("COMPLETE", resolution="effect_confirmed", decided_by="")
    assert model.outcome_copy(task_no_actor)["label"] == "Confirmed by a person"

    # Uncertain outcome
    task_unc = make_task("CANCELLED", resolution="cancelled_effect_unknown")
    outcome_unc = model.outcome_copy(task_unc)
    assert outcome_unc["outcome"] == model.OUTCOME_UNCERTAIN
    assert outcome_unc["mark"] == "gate-question"

def test_needs_you_card_cancel_requested_branch():
    task_blocked = make_task("BLOCKED", cancel_requested=True)
    card = model.needs_you_card(task_blocked, [])
    # When stop was requested, retry option is suppressed
    decisions = [c["decision"] for c in card["choices"]]
    assert "retry_authorized" not in decisions
    assert "effect_confirmed" in decisions
    assert "cancel" in decisions
    assert card["retry_unavailable_reason"] is not None

def test_home_partitioning_and_pagination():
    tasks = []
    # 5 needs_you, 10 working, 25 done
    for i in range(5):
        tasks.append(make_task("BLOCKED", task_id=f"ny-{i}"))
    for i in range(10):
        tasks.append(make_task("RUNNING", task_id=f"wk-{i}"))
    for i in range(25):
        tasks.append(make_task("COMPLETE", task_id=f"dn-{i}", resolution="verified"))

    h = model.home(tasks, {}, done_limit=15)
    assert h["counts"]["needs_you"] == 5
    assert h["counts"]["working"] == 10
    assert h["counts"]["done"] == 25
    assert len(h["needs_you"]) == 5
    assert len(h["working"]) == 10
    assert len(h["done"]) == 15
    assert h["done_shown"] == 15

def test_support_view_structure():
    task_dict = {
        "task_id": "t-1",
        "status": "RUNNING",
        "dispatch_id": "dsp-101",
        "worker_id": "w-42",
        "effect_class": "non_idempotent",
        "adapter": "synthetic",
        "params": {}
    }
    events = [{"type": "TASK_CREATED", "at": 1000.0}]
    sup = model.support(task_dict, events)
    assert sup["task"]["task_id"] == "t-1"
    assert sup["task"]["status"] == "RUNNING"
    assert sup["task"]["dispatch_id"] == "dsp-101"
    assert sup["task"]["worker_id"] == "w-42"
    assert len(sup["events"]) == 1
