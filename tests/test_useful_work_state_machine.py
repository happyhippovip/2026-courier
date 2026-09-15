import pytest
from scripts.useful_work_selection_engine import UsefulWorkSelectionEngine, AutonomyLifecycleState, WorkReadinessState

def test_empty_queue():
    engine = UsefulWorkSelectionEngine()
    res = engine.select_next_task([])
    # Note: discovering local useful work may yield tasks. We mock discover_grounded_useful_work
    engine.discover_grounded_useful_work = lambda: []
    res = engine.select_next_task([])
    assert res["lifecycle_state"] == AutonomyLifecycleState.QUEUE_EMPTY.value
    assert res["reason"] == "QUEUE_EMPTY_NOT_COMPLETE"

def test_gate_only():
    engine = UsefulWorkSelectionEngine()
    engine.discover_grounded_useful_work = lambda: []
    q = [{"objective": "test", "priority": 5.0, "source": "test"}]
    # Mock classify to return HUMAN_GATE
    engine.classify_opportunity = lambda o: (WorkReadinessState.HUMAN_GATE, "test")
    res = engine.select_next_task(q)
    assert res["lifecycle_state"] == AutonomyLifecycleState.HUMAN_GATE.value
    assert res["reason"] == "ONLY_HUMAN_GATED_WORK_REMAINS"

def test_dependency_only():
    engine = UsefulWorkSelectionEngine()
    engine.discover_grounded_useful_work = lambda: []
    q = [{"objective": "test", "priority": 5.0, "source": "test"}]
    engine.classify_opportunity = lambda o: (WorkReadinessState.BLOCKED_EXTERNAL, "test")
    res = engine.select_next_task(q)
    assert res["lifecycle_state"] == AutonomyLifecycleState.TASK_BLOCKED.value
    assert res["reason"] == "ONLY_DEPENDENCY_BLOCKED_WORK_REMAINS"

def test_gate_and_runnable():
    engine = UsefulWorkSelectionEngine()
    engine.discover_grounded_useful_work = lambda: []
    q = [
        {"objective": "blocked", "priority": 5.0, "source": "test"},
        {"objective": "runnable", "priority": 5.0, "source": "test"}
    ]
    def mock_classify(o):
        if o["objective"] == "blocked":
            return (WorkReadinessState.HUMAN_GATE, "test")
        return (WorkReadinessState.READY_USEFUL, "test")
    engine.classify_opportunity = mock_classify
    res = engine.select_next_task(q)
    assert res["lifecycle_state"] == AutonomyLifecycleState.TASK_RUNNING.value
    assert res["selected_task"]["objective"] == "runnable"
