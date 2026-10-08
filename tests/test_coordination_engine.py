from scripts.coordination_engine import CoordinationEngine, NextActionType
from scripts.coordination_ledger import (
    CoordinationReducer, CoordinationEvent, EventType, MissionStatus, AgentID, HostID
)

def create_event(eid, mid, etype, status, created_at, deps=None, blocker=None):
    return CoordinationEvent(
        event_id=eid,
        mission_id=mid,
        agent_id=AgentID.GOOGLE_WINDOWS,
        host_id=HostID.WINDOWS_REMOTE,
        event_type=etype,
        status=status,
        depends_on=deps or [],
        head="sha",
        evidence_ref="ref",
        created_at=created_at,
        payload_hash="hash",
        blocker=blocker
    )

def test_dag_evaluation():
    # 1. Worker A FINAL result unlocks dependent Worker B mission
    # 2. Worker B discovers A's result without manual copy/paste
    # 10. new worker/session can reconstruct current actionable state from durable shared truth.
    reducer = CoordinationReducer()
    
    e1 = create_event("1", "mission_A", EventType.FINAL, MissionStatus.DONE, "2026-10-07T12:00:00Z")
    reducer.apply(e1)
    
    e2 = create_event("2", "mission_B", EventType.ASSIGNED, MissionStatus.WORKING, "2026-10-07T12:00:00Z", deps=["mission_A"])
    reducer.apply(e2)
    
    # Another mission C dependent on something not done
    e3 = create_event("3", "mission_C", EventType.ASSIGNED, MissionStatus.WORKING, "2026-10-07T12:00:00Z", deps=["mission_D"])
    reducer.apply(e3)
    
    engine = CoordinationEngine(reducer)
    actions = engine.evaluate_dag()
    
    # mission_B should have an action (WAIT since it's WORKING, but it's evaluated)
    # mission_C should NOT be evaluated because mission_D is not done.
    evaluated_missions = [a.mission_id for a in actions]
    assert "mission_B" in evaluated_missions
    assert "mission_C" not in evaluated_missions

def test_blocked_does_not_freeze_unrelated():
    # 7. BLOCKED mission does not freeze unrelated DAG work.
    reducer = CoordinationReducer()
    
    e1 = create_event("1", "mission_blocked", EventType.BLOCKED, MissionStatus.BLOCKED, "2026-10-07T12:00:00Z", blocker="Needs secret")
    reducer.apply(e1)
    
    e2 = create_event("2", "mission_unrelated", EventType.ASSIGNED, MissionStatus.WORKING, "2026-10-07T12:00:00Z")
    reducer.apply(e2)
    
    engine = CoordinationEngine(reducer)
    actions = engine.evaluate_dag()
    
    evaluated_missions = [a.mission_id for a in actions]
    assert "mission_unrelated" in evaluated_missions
    assert "mission_blocked" in evaluated_missions
    
    for a in actions:
        if a.mission_id == "mission_blocked":
            assert a.action_type == NextActionType.HUMAN_ACTION_REQUIRED

def test_error_can_be_reconciled():
    # 8. ERROR can be reconciled/reassigned safely.
    reducer = CoordinationReducer()
    
    e1 = create_event("1", "mission_error", EventType.ERROR, MissionStatus.ERROR, "2026-10-07T12:00:00Z")
    reducer.apply(e1)
    
    engine = CoordinationEngine(reducer)
    actions = engine.evaluate_dag()
    
    error_action = next(a for a in actions if a.mission_id == "mission_error")
    assert error_action.action_type == NextActionType.CANCEL_REQUIRED

