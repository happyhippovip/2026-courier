from scripts.coordination_engine import CoordinationEngine
from scripts.coordination_ledger import CoordinationReducer, CoordinationEvent, AgentID, HostID, EventType, MissionStatus
from scripts.coordination_delivery import NextActionType

def test_coordination_engine_evaluate():
    reducer = CoordinationReducer()
    engine = CoordinationEngine(reducer)
    
    # Unknown mission
    action = engine.evaluate_next_action("m1")
    assert action.action_type == NextActionType.PREPARE_MISSION
    
    # Working mission
    reducer.apply(CoordinationEvent("1", "m1", AgentID.GOOGLE_WINDOWS, HostID.WINDOWS_REMOTE, EventType.ASSIGNED, MissionStatus.WORKING, [], "sha1", "ref", "time", "hash"))
    action = engine.evaluate_next_action("m1")
    assert action.action_type == NextActionType.WAIT
    
    # Done mission
    reducer.apply(CoordinationEvent("2", "m1", AgentID.GOOGLE_WINDOWS, HostID.WINDOWS_REMOTE, EventType.FINAL, MissionStatus.DONE, [], "sha2", "ref", "time", "hash"))
    action = engine.evaluate_next_action("m1")
    assert action.action_type == NextActionType.INTEGRATE_RESULTS
    
    # DAG Evaluation
    reducer.apply(CoordinationEvent("3", "m2", AgentID.GOOGLE_MAC, HostID.MAC_LOCAL, EventType.ASSIGNED, MissionStatus.WORKING, ["m1"], "sha3", "ref", "time", "hash"))
    actions = engine.evaluate_dag()
    assert len(actions) == 1
    assert actions[0].mission_id == "m2"
    assert actions[0].action_type == NextActionType.WAIT
